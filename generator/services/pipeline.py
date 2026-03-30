import sys
from typing import Any, Dict

from dotenv import load_dotenv

from generator.domain.models import GenerationContext, GenerationPaths, ProviderResult
from generator.services.io import file_exists, read_json_file, read_text_file, write_json_file
from generator.services.prompting import build_generation_prompt
from generator.services.providers import build_clients, generate_europass, resolve_anthropic_model, resolve_openai_model
from generator.utils.logging import log


def build_generation_context(paths: GenerationPaths) -> GenerationContext:
    job_data = read_json_file(paths.job_data_path)
    original_cv = read_text_file(paths.resume_path)
    prompt = build_generation_prompt(job_data, original_cv)

    return GenerationContext(
        job_data=job_data,
        original_cv=original_cv,
        prompt=prompt,
    )


def run_generation_pipeline(paths: GenerationPaths | None = None) -> Dict[str, Any]:
    load_dotenv()
    effective_paths = paths or GenerationPaths()

    log("Démarrage du batch generator.", "INFO")

    if not file_exists(effective_paths.job_data_path):
        log(
            f"Fichier requis introuvable : {effective_paths.job_data_path}. Generator est un job batch dépendant de analyzer et se termine sans erreur.",
            "INFO",
            sys.stderr,
        )
        return {"status": "skipped", "reason": "missing_job_data", "results": {}}

    if not file_exists(effective_paths.resume_path):
        raise FileNotFoundError(f"Fichier requis introuvable : {effective_paths.resume_path}")

    context = build_generation_context(effective_paths)
    generation_prompts = context.job_data.get("generation_prompts", {})

    log(
        f"Préparation du prompt de génération. Prompt spécifique trouvé : {'oui' if 'europass_cv_prompt' in generation_prompts else 'non, fallback utilisé'}.",
        "INFO",
    )
    log(f"Prompt final préparé ({len(context.prompt)} caractères).", "INFO")

    anthropic_client, openai_client = build_clients()
    context.anthropic_model = resolve_anthropic_model(anthropic_client) if anthropic_client is not None else None
    context.openai_model = resolve_openai_model(openai_client) if openai_client is not None else None

    for provider in ("anthropic", "openai"):
        try:
            provider_result = generate_europass(
                provider=provider,
                prompt=context.prompt,
                anthropic_client=anthropic_client,
                openai_client=openai_client,
                anthropic_model=context.anthropic_model,
                openai_model=context.openai_model,
            )
            context.results[provider] = provider_result.to_dict()
            log(f"Génération réussie pour le provider {provider}.", "INFO")
        except Exception as error:
            failed_result = ProviderResult(
                provider=provider,
                status="error",
                model=context.anthropic_model.id if provider == "anthropic" and context.anthropic_model else context.openai_model,
                error=str(error),
            )
            context.results[provider] = failed_result.to_dict()
            log(f"Échec génération {provider} : {error}", "WARN")

    if not context.results:
        raise RuntimeError("Aucun résultat généré.")

    write_json_file(effective_paths.results_path, context.results)

    success_count = sum(1 for provider_result in context.results.values() if provider_result.get("status") == "success")
    error_count = sum(1 for provider_result in context.results.values() if provider_result.get("status") == "error")
    log(
        f"Écriture terminée. Synthèse : {success_count} succès, {error_count} échec(s) provider.",
        "INFO",
    )

    return {
        "status": "success" if success_count > 0 else "error",
        "success_count": success_count,
        "error_count": error_count,
        "results": context.results,
        "output_path": effective_paths.results_path,
    }