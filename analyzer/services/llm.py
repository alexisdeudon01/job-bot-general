from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from analyzer.domain.models import NLPResult
from analyzer.utils.logging import log

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
MAX_CV_CHARS = 20000
MAX_JOB_TEXT_CHARS = 20000


class OpenAILLMService:
    """LLM service backed by OpenAI chat completions."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model or os.getenv("OPENAI_MODEL") or OPENAI_DEFAULT_MODEL
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def is_available(self) -> bool:
        return self.client is not None

    def current_model_id(self) -> str:
        return self._model

    def _chat(self, prompt: str, system: str = "", max_tokens: int = 8000) -> str:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY manquante.")

        raw_messages: list[dict[str, str]] = []
        if system:
            raw_messages.append({"role": "system", "content": system})
        raw_messages.append({"role": "user", "content": prompt})
        messages = cast(list[ChatCompletionMessageParam], raw_messages)

        response = self.client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return response.choices[0].message.content or ""

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response text."""
        cleaned = text.strip()
        # Try to strip markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            ).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            import re

            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        log(
            f"Impossible de parser le JSON LLM. Réponse brute : {cleaned[:500]}", "WARN"
        )
        return {}

    def analyze_cv(self, cv_text: str) -> Dict[str, Any]:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY manquante.")

        log(
            f"Lancement de l'analyse approfondie du CV via OpenAI ({len(cv_text)} caractères).",
            "INFO",
        )
        system = (
            "Tu es un expert RH. Analyse le CV fourni et retourne UNIQUEMENT un JSON valide, "
            "sans texte supplémentaire."
        )
        prompt = f"""Analyse en profondeur ce CV Europass. Extrait projets, entreprises et arguments forts.

CV :
{cv_text[:MAX_CV_CHARS]}

Retourne UNIQUEMENT un JSON :
{{
  "candidate_strengths": ["..."],
  "enriched_experiences": [{{"company": "...", "project": "...", "context": "...", "achievements": [...], "arguments_favor": [...]}}],
  "europass_sections": {{"summary": "...", "skills": [...]}}
}}"""
        response_text = self._chat(prompt, system=system, max_tokens=8000)
        result = self._extract_json(response_text)
        log(
            f"Analyse du CV via OpenAI terminée (modèle={self._model}).",
            "INFO",
        )
        return result

    def create_job_json(
        self,
        url: str,
        raw_text: str,
        nlp_result: NLPResult,
        cv_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY manquante.")

        log("Construction du JSON final d'analyse de poste via OpenAI...", "INFO")
        system = (
            "Tu es un expert en recrutement et stratégie de carrière. "
            "Retourne UNIQUEMENT un JSON valide, sans texte supplémentaire."
        )
        prompt = f"""Analyse l'offre et combine avec l'analyse du CV.

URL: {url}
Offre: {raw_text[:MAX_JOB_TEXT_CHARS]}
NLP: {nlp_result.to_dict()}
CV Analysis: {json.dumps(cv_analysis, ensure_ascii=False)}

Retourne UNIQUEMENT un JSON complet avec "candidate_analysis", "generation_prompts" (incluant europass_cv_prompt)."""
        response_text = self._chat(prompt, system=system, max_tokens=9000)
        result = self._extract_json(response_text)
        log(
            f"JSON final d'analyse de poste généré avec succès (modèle={self._model}).",
            "INFO",
        )
        return result


