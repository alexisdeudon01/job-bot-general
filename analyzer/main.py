import os
import json
import re
import sys
import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic
import spacy
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BLOCKED_MODELS = {
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-latest",
}
anthropic = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
_ANTHROPIC_MODEL_CACHE = None
PROMPT_CHAR_PER_TOKEN_ESTIMATE = 4
PROMPT_TOKEN_SAFETY_MARGIN = 600
MIN_INPUT_TOKEN_BUDGET = 1200


def log(message, level="INFO", stream=None):
    output = stream if stream is not None else (sys.stderr if level in ("ERREUR", "WARN") else sys.stdout)
    print(f"[ANALYZER][{level}] {message}", file=output, flush=True)


def load_spacy_model():
    log("Initialisation du moteur NLP spaCy...", "INFO")
    for model_name in ("fr_core_news_lg", "fr_core_news_md", "fr_core_news_sm"):
        try:
            model = spacy.load(model_name)
            log(f"Modèle spaCy chargé avec succès : {model_name}", "INFO")
            return model
        except OSError:
            log(f"Modèle spaCy indisponible : {model_name}", "WARN")

    log("Aucun modèle spaCy français installé, utilisation d'un mode dégradé sans NLP avancé.", "WARN")
    return None


nlp = load_spacy_model()


def scrape(url):
    log(f"Démarrage du scraping de l'offre depuis l'URL : {url}", "INFO")
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    log(f"Réponse HTTP reçue avec le statut {r.status_code}", "INFO")
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()
    extracted_text = soup.get_text(separator="\n", strip=True)[:30000]
    log(f"Scraping terminé, {len(extracted_text)} caractères de texte exploitable extraits.", "INFO")
    return extracted_text


def nlp_clean(text):
    log(f"Préparation NLP du texte de l'offre ({len(text)} caractères bruts)...", "INFO")
    if nlp is None:
        words = [word.strip(".,;:!?()[]{}\"'") for word in text.lower().split()]
        clean_tokens = [word for word in words if len(word) > 2]
        result = {
            "clean_text": " ".join(clean_tokens[:800]),
            "entities": [],
            "keywords": list(dict.fromkeys(clean_tokens))[:50],
        }
        log(
            f"Mode NLP dégradé terminé : {len(result['keywords'])} mots-clés retenus, aucune entité extraite.",
            "WARN",
        )
        return result

    doc = nlp(text.lower())
    clean_tokens = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and len(token.text) > 2]
    entities = [ent.text for ent in doc.ents]
    result = {
        "clean_text": " ".join(clean_tokens[:800]),
        "entities": list(set(entities))[:30],
        "keywords": list(set(clean_tokens))[:50]
    }
    log(
        f"NLP terminé : {len(result['keywords'])} mots-clés et {len(result['entities'])} entités détectés.",
        "INFO",
    )
    return result


def extract_positive_int_attribute(obj, attribute_names):
    for attribute_name in attribute_names:
        value = getattr(obj, attribute_name, None)
        if isinstance(value, int) and value > 0:
            return value
    return None


def resolve_anthropic_model():
    global _ANTHROPIC_MODEL_CACHE

    if anthropic is None:
        raise RuntimeError("ANTHROPIC_API_KEY manquante.")

    if _ANTHROPIC_MODEL_CACHE:
        return _ANTHROPIC_MODEL_CACHE

    log("Découverte dynamique des modèles Anthropic disponibles via l'API...", "INFO")
    models_page = anthropic.models.list(limit=100)
    available_models = [
        model
        for model in models_page.data
        if getattr(model, "id", None) and getattr(model, "id", None) not in ANTHROPIC_BLOCKED_MODELS
    ]

    if not available_models:
        raise RuntimeError("Aucun modèle Anthropic disponible pour cette clé API.")

    selected_model = available_models[0]
    _ANTHROPIC_MODEL_CACHE = {
        "id": selected_model.id,
        "output_token_limit": extract_positive_int_attribute(
            selected_model,
            ("output_token_limit", "max_output_tokens", "max_tokens", "max_completion_tokens"),
        ),
        "input_token_limit": extract_positive_int_attribute(
            selected_model,
            ("input_token_limit", "max_input_tokens", "context_window", "context_length"),
        ),
    }
    log(
        (
            f"Modèle Anthropic sélectionné automatiquement (1er disponible) : {_ANTHROPIC_MODEL_CACHE['id']} "
            f"(input_limit={_ANTHROPIC_MODEL_CACHE['input_token_limit']}, "
            f"output_limit={_ANTHROPIC_MODEL_CACHE['output_token_limit']})"
        ),
        "INFO",
    )
    return _ANTHROPIC_MODEL_CACHE


def infer_anthropic_max_tokens_from_error(error):
    error_message = str(error)
    match = re.search(r"max_tokens:\s*\d+\s*>\s*(\d+)", error_message)
    if match:
        return int(match.group(1))
    return None


def adapt_prompt_to_input_limit(prompt, input_token_limit, reserved_output_tokens):
    if not input_token_limit:
        return prompt

    allowed_input_tokens = max(
        MIN_INPUT_TOKEN_BUDGET,
        input_token_limit - reserved_output_tokens - PROMPT_TOKEN_SAFETY_MARGIN,
    )
    max_chars = allowed_input_tokens * PROMPT_CHAR_PER_TOKEN_ESTIMATE

    if len(prompt) <= max_chars:
        return prompt

    log(
        (
            f"Prompt tronqué automatiquement pour respecter la fenêtre d'entrée du modèle "
            f"(longueur initiale={len(prompt)}, longueur max={max_chars})."
        ),
        "WARN",
    )
    return (
        prompt[:max_chars]
        + "\n\n[NOTE TECHNIQUE] Prompt tronqué automatiquement pour respecter la limite de contexte du modèle."
    )


def get_anthropic_client():
    if anthropic is None:
        raise RuntimeError("ANTHROPIC_API_KEY manquante.")
    return anthropic


def extract_anthropic_text(response):
    text_parts = []
    for block in getattr(response, "content", []) or []:
        block_text = getattr(block, "text", None)
        if isinstance(block_text, str) and block_text.strip():
            text_parts.append(block_text)

    if not text_parts:
        raise RuntimeError("Réponse Anthropic sans contenu textuel exploitable.")

    return "\n".join(text_parts)


def create_anthropic_message_with_adaptive_tokens(prompt, requested_max_tokens):
    anthropic_client = get_anthropic_client()
    model_info = resolve_anthropic_model()
    model_name = model_info["id"]
    model_output_limit = model_info.get("output_token_limit")
    effective_max_tokens = min(requested_max_tokens, model_output_limit) if model_output_limit else requested_max_tokens
    adapted_prompt = adapt_prompt_to_input_limit(
        prompt=prompt,
        input_token_limit=model_info.get("input_token_limit"),
        reserved_output_tokens=effective_max_tokens,
    )

    try:
        response = anthropic_client.messages.create(
            model=model_name,
            max_tokens=effective_max_tokens,
            messages=[{"role": "user", "content": adapted_prompt}],
        )
        return response, model_name, effective_max_tokens
    except Exception as error:
        allowed_max_tokens = infer_anthropic_max_tokens_from_error(error)
        if not allowed_max_tokens:
            raise

        log(
            (
                f"Anthropic a refusé max_tokens={effective_max_tokens}. "
                f"Nouvelle tentative avec la limite détectée: {allowed_max_tokens}."
            ),
            "WARN",
        )
        adapted_prompt = adapt_prompt_to_input_limit(
            prompt=prompt,
            input_token_limit=model_info.get("input_token_limit"),
            reserved_output_tokens=allowed_max_tokens,
        )
        response = anthropic_client.messages.create(
            model=model_name,
            max_tokens=allowed_max_tokens,
            messages=[{"role": "user", "content": adapted_prompt}],
        )
        return response, model_name, allowed_max_tokens


def extract_json(text):
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def build_fallback_cv_analysis(cv_text):
    preview = cv_text.strip()[:500]
    strengths = []
    if cv_text.strip():
        strengths.append("CV source fourni")
    else:
        strengths.append("CV source vide ou non renseigné")

    return {
        "candidate_strengths": strengths,
        "enriched_experiences": [],
        "europass_sections": {
            "summary": preview,
            "skills": [],
        },
        "_meta": {
            "mode": "fallback",
            "llm_provider": "anthropic",
            "llm_status": "unavailable_or_failed",
        },
    }


def build_fallback_job_json(url, raw_text, cv_text, nlp_result, cv_analysis, error_message):
    keywords = nlp_result.get("keywords", [])[:20] if isinstance(nlp_result, dict) else []
    entities = nlp_result.get("entities", [])[:20] if isinstance(nlp_result, dict) else []

    return {
        "source": {
            "job_url": url,
            "scraped_chars": len(raw_text),
            "cv_chars": len(cv_text),
        },
        "candidate_analysis": {
            "strengths": cv_analysis.get("candidate_strengths", []),
            "entities": entities,
            "keywords": keywords,
            "summary": "Analyse générée en mode dégradé suite à un échec ou une indisponibilité du modèle Anthropic.",
        },
        "generation_prompts": {
            "europass_cv_prompt": (
                "À partir des mots-clés, entités et du CV fourni, produire une adaptation Europass ciblée pour cette offre."
            )
        },
        "debug": {
            "fallback_reason": error_message,
            "anthropic_model": (_ANTHROPIC_MODEL_CACHE or {}).get("id", "auto-detect"),
            "llm_provider": "anthropic",
            "mode": "fallback",
        },
    }


def deep_cv_analysis(cv_text):
    if anthropic is None:
        raise RuntimeError("ANTHROPIC_API_KEY manquante.")

    log(
        f"Lancement de l'analyse approfondie du CV via Anthropic ({len(cv_text)} caractères de CV fournis).",
        "INFO",
    )
    prompt = f"""
Analyse en profondeur ce CV Europass. Extrait projets, entreprises et arguments forts.

CV :
{cv_text[:20000]}

Retourne UNIQUEMENT un JSON :
{{
  "candidate_strengths": ["..."],
  "enriched_experiences": [{{ "company": "...", "project": "...", "context": "...", "achievements": [...], "arguments_favor": [...] }}],
  "europass_sections": {{ "summary": "...", "skills": [...] }}
}}
"""
    resp, model_name, used_max_tokens = create_anthropic_message_with_adaptive_tokens(
        prompt=prompt,
        requested_max_tokens=8000,
    )
    result = extract_json(extract_anthropic_text(resp))
    log(f"Analyse du CV via Anthropic terminée avec succès (modèle={model_name}, max_tokens={used_max_tokens}).", "INFO")
    return result


def create_job_json(url, raw_text, cv_text, nlp_result, cv_analysis):
    if anthropic is None:
        raise RuntimeError("ANTHROPIC_API_KEY manquante.")

    log("Construction du JSON final d'analyse de poste via Anthropic...", "INFO")
    prompt = f"""
Analyse l'offre et combine avec l'analyse du CV.

URL: {url}
Offre: {raw_text[:20000]}
NLP: {nlp_result}
CV Analysis: {json.dumps(cv_analysis, ensure_ascii=False)}

Retourne UNIQUEMENT un JSON complet avec "candidate_analysis", "generation_prompts" (incluant europass_cv_prompt).
"""
    response, model_name, used_max_tokens = create_anthropic_message_with_adaptive_tokens(
        prompt=prompt,
        requested_max_tokens=9000,
    )
    result = extract_json(extract_anthropic_text(response))
    log(
        f"JSON final d'analyse de poste généré avec succès (modèle={model_name}, max_tokens={used_max_tokens}).",
        "INFO",
    )
    return result


if __name__ == "__main__":
    url = os.getenv("JOB_URL", "").strip()

    if not url:
        log("Aucun JOB_URL fourni : analyzer est un job batch one-shot et se termine sans erreur.", "INFO")
        sys.exit(0)

    try:
        log("Démarrage du batch analyzer.", "INFO")

        cv_path = "/data/resume_europass.txt"
        log(f"Lecture du CV source depuis {cv_path}...", "INFO")
        with open(cv_path, "r", encoding="utf-8") as f:
            cv_text = f.read()
        log(f"CV chargé avec succès ({len(cv_text)} caractères).", "INFO")

        if not cv_text.strip():
            log("Le CV source est vide : l'analyse continuera, mais le résultat sera limité.", "WARN")

        raw = scrape(url)
        nlp_res = nlp_clean(raw)

        fallback_reason = None

        if anthropic is None:
            fallback_reason = "ANTHROPIC_API_KEY absente."
            log("ANTHROPIC_API_KEY absente : bascule en mode fallback pour produire malgré tout `job_data.json`.", "WARN")
            cv_analysis = build_fallback_cv_analysis(cv_text)
            job_json = build_fallback_job_json(url, raw, cv_text, nlp_res, cv_analysis, fallback_reason)
        else:
            try:
                cv_analysis = deep_cv_analysis(cv_text)
                job_json = create_job_json(url, raw, cv_text, nlp_res, cv_analysis)
            except Exception as llm_error:
                fallback_reason = str(llm_error)
                log(
                    f"Échec de l'analyse LLM Anthropic, bascule en mode fallback pour générer `job_data.json` : {fallback_reason}",
                    "WARN",
                )
                cv_analysis = build_fallback_cv_analysis(cv_text)
                job_json = build_fallback_job_json(url, raw, cv_text, nlp_res, cv_analysis, fallback_reason)

        output_path = "/output/job_data.json"
        log(f"Écriture du fichier d'analyse final dans {output_path}...", "INFO")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(job_json, f, ensure_ascii=False, indent=2)

        if fallback_reason:
            log("Analyse terminée en mode dégradé avec génération locale du JSON.", "WARN")
            print("⚠️ Analyse terminée en mode fallback")
        else:
            log("Analyse terminée avec succès.", "INFO")
            print("✅ Analyse terminée")
    except Exception as error:
        log(f"Échec du batch analyzer : {error}", "ERREUR")
        raise
