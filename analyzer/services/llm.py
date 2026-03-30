import json
import os
import re
from typing import Any, Dict, Optional

from anthropic import Anthropic

from analyzer.domain.models import NLPResult
from analyzer.utils.logging import log

ANTHROPIC_BLOCKED_MODELS = {
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-latest",
}
PROMPT_CHAR_PER_TOKEN_ESTIMATE = 4
PROMPT_TOKEN_SAFETY_MARGIN = 600
MIN_INPUT_TOKEN_BUDGET = 1200


def extract_positive_int_attribute(obj: Any, attribute_names):
    for attribute_name in attribute_names:
        value = getattr(obj, attribute_name, None)
        if isinstance(value, int) and value > 0:
            return value
    return None


class AnthropicLLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
        self._model_cache: Optional[Dict[str, Any]] = None

    def is_available(self) -> bool:
        return self.client is not None

    def resolve_model(self) -> Dict[str, Any]:
        if self.client is None:
            raise RuntimeError("ANTHROPIC_API_KEY manquante.")

        if self._model_cache:
            return self._model_cache

        log("Découverte dynamique des modèles Anthropic disponibles via l'API...", "INFO")
        models_page = self.client.models.list(limit=100)
        available_models = [
            model
            for model in models_page.data
            if getattr(model, "id", None) and getattr(model, "id", None) not in ANTHROPIC_BLOCKED_MODELS
        ]

        if not available_models:
            raise RuntimeError("Aucun modèle Anthropic disponible pour cette clé API.")

        selected_model = available_models[0]
        self._model_cache = {
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
                f"Modèle Anthropic sélectionné automatiquement (1er disponible) : {self._model_cache['id']} "
                f"(input_limit={self._model_cache['input_token_limit']}, "
                f"output_limit={self._model_cache['output_token_limit']})"
            ),
            "INFO",
        )
        return self._model_cache

    @staticmethod
    def infer_max_tokens_from_error(error: Exception) -> Optional[int]:
        error_message = str(error)
        match = re.search(r"max_tokens:\s*\d+\s*>\s*(\d+)", error_message)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def adapt_prompt_to_input_limit(prompt: str, input_token_limit: Optional[int], reserved_output_tokens: int) -> str:
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

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        cleaned_text = text.strip()
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned_text, re.DOTALL)
        if match:
            cleaned_text = match.group(1).strip()
        return json.loads(cleaned_text)

    @staticmethod
    def extract_text(response: Any) -> str:
        text_parts = []
        for block in getattr(response, "content", []) or []:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str) and block_text.strip():
                text_parts.append(block_text)

        if not text_parts:
            raise RuntimeError("Réponse Anthropic sans contenu textuel exploitable.")

        return "\n".join(text_parts)

    def create_message(self, prompt: str, requested_max_tokens: int):
        if self.client is None:
            raise RuntimeError("ANTHROPIC_API_KEY manquante.")

        model_info = self.resolve_model()
        model_name = model_info["id"]
        model_output_limit = model_info.get("output_token_limit")
        effective_max_tokens = min(requested_max_tokens, model_output_limit) if model_output_limit else requested_max_tokens
        adapted_prompt = self.adapt_prompt_to_input_limit(
            prompt=prompt,
            input_token_limit=model_info.get("input_token_limit"),
            reserved_output_tokens=effective_max_tokens,
        )

        try:
            response = self.client.messages.create(
                model=model_name,
                max_tokens=effective_max_tokens,
                messages=[{"role": "user", "content": adapted_prompt}],
            )
            return response, model_name, effective_max_tokens
        except Exception as error:
            allowed_max_tokens = self.infer_max_tokens_from_error(error)
            if not allowed_max_tokens:
                raise

            log(
                (
                    f"Anthropic a refusé max_tokens={effective_max_tokens}. "
                    f"Nouvelle tentative avec la limite détectée: {allowed_max_tokens}."
                ),
                "WARN",
            )
            adapted_prompt = self.adapt_prompt_to_input_limit(
                prompt=prompt,
                input_token_limit=model_info.get("input_token_limit"),
                reserved_output_tokens=allowed_max_tokens,
            )
            response = self.client.messages.create(
                model=model_name,
                max_tokens=allowed_max_tokens,
                messages=[{"role": "user", "content": adapted_prompt}],
            )
            return response, model_name, allowed_max_tokens

    def analyze_cv(self, cv_text: str) -> Dict[str, Any]:
        if self.client is None:
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
        response, model_name, used_max_tokens = self.create_message(prompt=prompt, requested_max_tokens=8000)
        result = self.extract_json(self.extract_text(response))
        log(
            f"Analyse du CV via Anthropic terminée avec succès (modèle={model_name}, max_tokens={used_max_tokens}).",
            "INFO",
        )
        return result

    def create_job_json(self, url: str, raw_text: str, nlp_result: NLPResult, cv_analysis: Dict[str, Any]) -> Dict[str, Any]:
        if self.client is None:
            raise RuntimeError("ANTHROPIC_API_KEY manquante.")

        log("Construction du JSON final d'analyse de poste via Anthropic...", "INFO")
        prompt = f"""
Analyse l'offre et combine avec l'analyse du CV.

URL: {url}
Offre: {raw_text[:20000]}
NLP: {nlp_result.to_dict()}
CV Analysis: {json.dumps(cv_analysis, ensure_ascii=False)}

Retourne UNIQUEMENT un JSON complet avec "candidate_analysis", "generation_prompts" (incluant europass_cv_prompt).
"""
        response, model_name, used_max_tokens = self.create_message(prompt=prompt, requested_max_tokens=9000)
        result = self.extract_json(self.extract_text(response))
        log(
            f"JSON final d'analyse de poste généré avec succès (modèle={model_name}, max_tokens={used_max_tokens}).",
            "INFO",
        )
        return result

    def current_model_id(self) -> str:
        if self._model_cache:
            return self._model_cache.get("id", "auto-detect")
        return "auto-detect"