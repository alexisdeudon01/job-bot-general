from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from generator.domain.models import ProviderResult
from generator.utils.logging import log

PROMPT_CHAR_PER_TOKEN_ESTIMATE = 4
PROMPT_TOKEN_SAFETY_MARGIN = 600
MIN_INPUT_TOKEN_BUDGET = 1202


def build_openai_client() -> Optional[OpenAI]:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    log(
        f"Vérification du provider IA : OpenAI={'prêt' if openai_api_key else 'non configuré'}.",
        "INFO",
    )
    return OpenAI(api_key=openai_api_key) if openai_api_key else None


def resolve_openai_model(openai_client: Optional[OpenAI]) -> str:
    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY manquante")

    log("Découverte dynamique des modèles OpenAI disponibles via l'API...", "INFO")
    models_page = openai_client.models.list()
    available_models = [getattr(model, "id", None) for model in models_page.data]
    available_models = [model_id for model_id in available_models if model_id]

    if not available_models:
        raise RuntimeError("Aucun modèle OpenAI disponible pour cette clé API")

    preferred = [m for m in available_models if "gpt-4o" in m or "gpt-4" in m]
    selected = preferred[0] if preferred else available_models[0]
    log(f"Modèle OpenAI sélectionné : {selected}", "INFO")
    return selected


def adapt_prompt_to_input_limit(
    prompt: str,
    input_token_limit: Optional[int],
    reserved_output_tokens: int,
) -> str:
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


def generate_europass(
    prompt: str,
    openai_client: Optional[OpenAI],
    openai_model: Optional[str],
    provider: str = "openai",
) -> ProviderResult:
    """Generate a Europass CV using OpenAI chat completions."""
    log(f"Démarrage de la génération Europass avec le provider : {provider}", "INFO")

    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY manquante")
    if not openai_model:
        raise RuntimeError("Aucun modèle OpenAI résolu")

    log("Appel API OpenAI en cours...", "INFO")
    response = openai_client.chat.completions.create(
        model=openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un assistant expert RH. Tu dois produire directement un CV Europass complet "
                    "et exploitable en français à partir du contexte fourni. Ne demande jamais "
                    "d'informations supplémentaires si le contexte contient déjà une offre, des mots-clés, "
                    "des entités ou un CV source, même partiel. Si des données manquent, complète au mieux "
                    "sans poser de question."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    text = response.choices[0].message.content
    log(f"Réponse OpenAI reçue ({len(text) if text else 0} caractères).", "INFO")

    lowered_text = (text or "").lower()
    if "veuillez fournir" in lowered_text or "merci de fournir" in lowered_text:
        raise RuntimeError(
            "Le provider OpenAI a demandé des informations supplémentaires au lieu de générer le CV final"
        )

    return ProviderResult(
        provider="openai",
        status="success",
        model=openai_model,
        europass_cv=text,
    )
