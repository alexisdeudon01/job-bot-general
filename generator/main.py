import json
import os
import re
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

JOB_DATA_PATH = "/output/job_data.json"
RESUME_PATH = "/data/resume_europass.txt"
RESULTS_PATH = "/output/generation_results.json"
DEFAULT_ANTHROPIC_MAX_TOKENS = 6000
PROMPT_CHAR_PER_TOKEN_ESTIMATE = 4
PROMPT_TOKEN_SAFETY_MARGIN = 600
MIN_INPUT_TOKEN_BUDGET = 1200


def log(message, level="INFO", stream=None):
    output = stream if stream is not None else (sys.stderr if level in ("ERREUR", "WARN") else sys.stdout)
    print(f"[GENERATOR][{level}] {message}", file=output, flush=True)


def read_text_file(path):
    log(f"Lecture du fichier texte : {path}", "INFO")
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
    log(f"Fichier texte chargé ({len(content)} caractères).", "INFO")
    return content


def read_json_file(path):
    log(f"Lecture du fichier JSON : {path}", "INFO")
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    log(f"Fichier JSON chargé avec succès. Clés principales : {list(data.keys())}", "INFO")
    return data


def extract_positive_int_attribute(obj, attribute_names):
    for attribute_name in attribute_names:
        value = getattr(obj, attribute_name, None)
        if isinstance(value, int) and value > 0:
            return value
    return None


def resolve_anthropic_model(anthropic_client):
    if anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY manquante")

    log("Découverte dynamique des modèles Anthropic disponibles via l'API...", "INFO")
    models_page = anthropic_client.models.list(limit=100)
    available_models = [model for model in models_page.data if getattr(model, "id", None)]

    if not available_models:
        raise RuntimeError("Aucun modèle Anthropic disponible pour cette clé API")

    selected_model = available_models[0]
    model_info = {
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
            f"Modèle Anthropic sélectionné automatiquement (1er disponible) : {model_info['id']} "
            f"(input_limit={model_info['input_token_limit']}, output_limit={model_info['output_token_limit']})"
        ),
        "INFO",
    )
    return model_info


def resolve_openai_model(openai_client):
    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY manquante")

    log("Découverte dynamique des modèles OpenAI disponibles via l'API...", "INFO")
    models_page = openai_client.models.list()
    available_models = [getattr(model, "id", None) for model in models_page.data]
    available_models = [model_id for model_id in available_models if model_id]

    if not available_models:
        raise RuntimeError("Aucun modèle OpenAI disponible pour cette clé API")

    log(f"Modèle OpenAI sélectionné automatiquement (1er disponible) : {available_models[0]}", "INFO")
    return available_models[0]


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


def create_anthropic_message_with_adaptive_tokens(anthropic_client, model_info, prompt, requested_max_tokens):
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
        return response, effective_max_tokens
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
        return response, allowed_max_tokens


def build_clients():
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    log(
        f"Vérification des providers IA : Anthropic={'prêt' if anthropic_api_key else 'non configuré'}, OpenAI={'prêt' if openai_api_key else 'non configuré'}.",
        "INFO",
    )

    anthropic_client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None
    openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

    return anthropic_client, openai_client


def generate_europass(provider, prompt, anthropic_client, openai_client, anthropic_model, openai_model):
    log(f"Démarrage de la génération Europass avec le provider : {provider}", "INFO")

    if provider == "anthropic":
        if anthropic_client is None:
            raise RuntimeError("ANTHROPIC_API_KEY manquante")
        if not anthropic_model:
            raise RuntimeError("Aucun modèle Anthropic résolu")

        log("Appel API Anthropic en cours...", "INFO")
        response, used_max_tokens = create_anthropic_message_with_adaptive_tokens(
            anthropic_client=anthropic_client,
            model_info=anthropic_model,
            prompt=prompt,
            requested_max_tokens=DEFAULT_ANTHROPIC_MAX_TOKENS,
        )
        text = response.content[0].text
        log(f"Réponse Anthropic reçue ({len(text)} caractères, max_tokens={used_max_tokens}).", "INFO")
        return {
            "provider": provider,
            "status": "success",
            "model": anthropic_model["id"],
            "europass_cv": text,
        }

    if provider == "openai":
        if openai_client is None:
            raise RuntimeError("OPENAI_API_KEY manquante")
        if not openai_model:
            raise RuntimeError("Aucun modèle OpenAI résolu")
        model_name = openai_model
        log("Appel API OpenAI en cours...", "INFO")
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un assistant expert RH. Tu dois produire directement un CV Europass complet et exploitable en français à partir du contexte fourni. Ne demande jamais d'informations supplémentaires si le contexte contient déjà une offre, des mots-clés, des entités ou un CV source, même partiel. Si des données manquent, complète au mieux sans poser de question.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        text = response.choices[0].message.content
        log(f"Réponse OpenAI reçue ({len(text) if text else 0} caractères).", "INFO")
        lowered_text = (text or "").lower()
        if "veuillez fournir" in lowered_text or "merci de fournir" in lowered_text:
            raise RuntimeError("Le provider OpenAI a demandé des informations supplémentaires au lieu de générer le CV final")

        return {
            "provider": provider,
            "status": "success",
            "model": model_name,
            "europass_cv": text,
        }

    raise ValueError(f"Provider inconnu: {provider}")


def build_generation_prompt(job_data, original_cv):
    candidate_analysis = job_data.get("candidate_analysis", {})
    generation_prompts = job_data.get("generation_prompts", {})

    base_prompt = generation_prompts.get(
        "europass_cv_prompt",
        "Adapte ce CV au format Europass structuré",
    )

    prompt_sections = [
        "Tu dois produire directement un CV Europass complet en français.",
        "N'ajoute aucune question.",
        "N'indique pas que des informations manquent.",
        "Si certaines données sont absentes, complète de manière professionnelle et cohérente.",
        "",
        "=== CONTEXTE OFFRE ET CANDIDAT ===",
        json.dumps(
            {
                "candidate_analysis": candidate_analysis,
                "generation_prompts": generation_prompts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "=== INSTRUCTION CIBLE ===",
        base_prompt,
        "",
        "=== CV ORIGINAL ===",
        original_cv,
        "",
        "=== FORMAT ATTENDU ===",
        "Retourne uniquement le CV final rédigé, prêt à être utilisé.",
    ]

    return "\n".join(prompt_sections)


def main():
    log("Démarrage du batch generator.", "INFO")

    if not os.path.exists(JOB_DATA_PATH):
        log(
            f"Fichier requis introuvable : {JOB_DATA_PATH}. Generator est un job batch dépendant de analyzer et se termine sans erreur.",
            "INFO",
            sys.stderr,
        )
        sys.exit(0)

    if not os.path.exists(RESUME_PATH):
        log(f"Fichier requis introuvable : {RESUME_PATH}", "ERREUR")
        sys.exit(1)

    try:
        job_data = read_json_file(JOB_DATA_PATH)
        original_cv = read_text_file(RESUME_PATH)
        generation_prompts = job_data.get("generation_prompts", {})

        log(
            f"Préparation du prompt de génération. Prompt spécifique trouvé : {'oui' if 'europass_cv_prompt' in generation_prompts else 'non, fallback utilisé'}.",
            "INFO",
        )
        prompt = build_generation_prompt(job_data, original_cv)
        log(f"Prompt final préparé ({len(prompt)} caractères).", "INFO")

        anthropic_client, openai_client = build_clients()

        results = {}

        anthropic_model = resolve_anthropic_model(anthropic_client) if anthropic_client is not None else None
        openai_model = resolve_openai_model(openai_client) if openai_client is not None else None

        for provider in ("anthropic", "openai"):
            try:
                provider_result = generate_europass(
                    provider,
                    prompt,
                    anthropic_client,
                    openai_client,
                    anthropic_model,
                    openai_model,
                )
                results[provider] = provider_result
                log(f"Génération réussie pour le provider {provider}.", "INFO")
            except Exception as error:
                results[provider] = {
                    "provider": provider,
                    "status": "error",
                    "model": anthropic_model["id"] if provider == "anthropic" and anthropic_model else openai_model,
                    "error": str(error),
                }
                log(f"Échec génération {provider} : {error}", "WARN")

        if not results:
            log("Aucun résultat généré.", "ERREUR")
            sys.exit(1)

        log(f"Écriture des résultats de génération dans {RESULTS_PATH}...", "INFO")
        with open(RESULTS_PATH, "w", encoding="utf-8") as file:
            json.dump(results, file, ensure_ascii=False, indent=2)

        success_count = sum(1 for provider_result in results.values() if provider_result.get("status") == "success")
        error_count = sum(1 for provider_result in results.values() if provider_result.get("status") == "error")
        log(
            f"Écriture terminée. Synthèse : {success_count} succès, {error_count} échec(s) provider.",
            "INFO",
        )

        if any(provider_result.get("status") == "success" for provider_result in results.values()):
            print("✅ CV Europass générés")
            return

        log("Aucun provider n'a pu générer de CV.", "ERREUR")
        sys.exit(1)
    except Exception as error:
        log(f"Échec global du batch generator : {error}", "ERREUR")
        raise


if __name__ == "__main__":
    main()
