import json
import os
from typing import Any, Dict

from analyzer.domain.models import AnalyzerArtifacts
from analyzer.services.llm import AnthropicLLMService
from analyzer.services.nlp import NLPService
from analyzer.services.scraper import scrape_job_offer
from analyzer.utils.logging import log


def build_fallback_cv_analysis(cv_text: str) -> Dict[str, Any]:
    preview = cv_text.strip()[:500]
    strengths = ["CV source fourni"] if cv_text.strip() else ["CV source vide ou non renseigné"]

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


def build_fallback_job_json(
    url: str,
    raw_text: str,
    cv_text: str,
    nlp_result,
    cv_analysis: Dict[str, Any],
    error_message: str,
    anthropic_model: str,
) -> Dict[str, Any]:
    keywords = nlp_result.keywords[:20]
    entities = nlp_result.entities[:20]

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
            "europass_cv_prompt": "À partir des mots-clés, entités et du CV fourni, produire une adaptation Europass ciblée pour cette offre."
        },
        "debug": {
            "fallback_reason": error_message,
            "anthropic_model": anthropic_model,
            "llm_provider": "anthropic",
            "mode": "fallback",
        },
    }


class AnalyzerPipeline:
    def __init__(self, nlp_service: NLPService, llm_service: AnthropicLLMService):
        self.nlp_service = nlp_service
        self.llm_service = llm_service

    def load_cv_text(self, cv_path: str) -> str:
        log(f"Lecture du CV source depuis {cv_path}...", "INFO")
        with open(cv_path, "r", encoding="utf-8") as file:
            cv_text = file.read()
        log(f"CV chargé avec succès ({len(cv_text)} caractères).", "INFO")

        if not cv_text.strip():
            log("Le CV source est vide : l'analyse continuera, mais le résultat sera limité.", "WARN")

        return cv_text

    def run(self, job_url: str, cv_path: str = "/data/resume_europass.txt") -> AnalyzerArtifacts:
        cv_text = self.load_cv_text(cv_path)
        raw_job_text = scrape_job_offer(job_url)
        nlp_result = self.nlp_service.clean(raw_job_text)

        fallback_reason = None

        if not self.llm_service.is_available():
            fallback_reason = "ANTHROPIC_API_KEY absente."
            log("ANTHROPIC_API_KEY absente : bascule en mode fallback pour produire malgré tout `job_data.json`.", "WARN")
            cv_analysis = build_fallback_cv_analysis(cv_text)
            job_json = build_fallback_job_json(
                url=job_url,
                raw_text=raw_job_text,
                cv_text=cv_text,
                nlp_result=nlp_result,
                cv_analysis=cv_analysis,
                error_message=fallback_reason,
                anthropic_model=self.llm_service.current_model_id(),
            )
        else:
            try:
                cv_analysis = self.llm_service.analyze_cv(cv_text)
                job_json = self.llm_service.create_job_json(job_url, raw_job_text, nlp_result, cv_analysis)
            except Exception as llm_error:
                fallback_reason = str(llm_error)
                log(
                    f"Échec de l'analyse LLM Anthropic, bascule en mode fallback pour générer `job_data.json` : {fallback_reason}",
                    "WARN",
                )
                cv_analysis = build_fallback_cv_analysis(cv_text)
                job_json = build_fallback_job_json(
                    url=job_url,
                    raw_text=raw_job_text,
                    cv_text=cv_text,
                    nlp_result=nlp_result,
                    cv_analysis=cv_analysis,
                    error_message=fallback_reason,
                    anthropic_model=self.llm_service.current_model_id(),
                )

        return AnalyzerArtifacts(
            job_url=job_url,
            cv_text=cv_text,
            raw_job_text=raw_job_text,
            nlp_result=nlp_result,
            cv_analysis=cv_analysis,
            job_json=job_json,
            fallback_reason=fallback_reason,
        )

    def write_output(self, job_json: Dict[str, Any], output_path: str = "/output/job_data.json") -> None:
        log(f"Écriture du fichier d'analyse final dans {output_path}...", "INFO")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(job_json, file, ensure_ascii=False, indent=2)


def create_default_pipeline() -> AnalyzerPipeline:
    return AnalyzerPipeline(
        nlp_service=NLPService(),
        llm_service=AnthropicLLMService(),
    )