import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

JOB_DATA_PATH = "/output/job_data.json"
RESUME_PATH = "/data/resume_europass.txt"
RESULTS_PATH = "/output/generation_results.json"


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


def resolve_anthropic_model(anthropic_client):
    if anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY manquante")

    log("Découverte dynamique des modèles Anthropic disponibles via l'API...", "INFO")
    models_page = anthropic_client.models.list(limit=100)
    available_models = [getattr(model, "id", None) for model in models_page.data]
    available_models = [model_id for model_id in available_models if model_id]

    if not available_models:
        raise RuntimeError("Aucun modèle Anthropic disponible pour cette clé API")

    log(f"Modèle Anthropic sélectionné automatiquement (1er disponible) : {available_models[0]}", "INFO")
    return available_models[0]


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
        log("Appel API Anthropic en cours...", "INFO")
        response = anthropic_client.messages.create(
            model=anthropic_model,
            max_tokens=6000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        log(f"Réponse Anthropic reçue ({len(text)} caractères).", "INFO")
        return {
            "provider": provider,
            "status": "success",
            "model": anthropic_model,
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
                    "model": anthropic_model if provider == "anthropic" else openai_model,
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
