import json
import os
from typing import Any, Dict, Optional

from analyzer.domain.models import AnalyzerArtifacts
from analyzer.services.llm import OpenAILLMService
from analyzer.services.nlp import NLPService
from analyzer.services.scraper import scrape_job_offer, scrape_job_offer_structured
from analyzer.utils.logging import log


def build_fallback_cv_analysis(cv_text: str) -> Dict[str, Any]:
    preview = cv_text.strip()[:500]
    strengths = (
        ["CV source fourni"] if cv_text.strip() else ["CV source vide ou non renseigné"]
    )

    return {
        "candidate_strengths": strengths,
        "enriched_experiences": [],
        "europass_sections": {
            "summary": preview,
            "skills": [],
        },
        "_meta": {
            "mode": "fallback",
            "llm_provider": "openai",
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
    openai_model: str,
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
            "summary": "Analyse générée en mode dégradé suite à un échec ou une indisponibilité du modèle OpenAI.",
        },
        "generation_prompts": {
            "europass_cv_prompt": "À partir des mots-clés, entités et du CV fourni, produire une adaptation Europass ciblée pour cette offre."
        },
        "debug": {
            "fallback_reason": error_message,
            "openai_model": openai_model,
            "llm_provider": "openai",
            "mode": "fallback",
        },
    }


def enrich_job_json_with_scraping_metadata(
    job_json: Dict[str, Any],
    job_url: str,
    raw_job_text: str,
    job_offer_structured: Optional[Dict[str, Any]],
    scraping_source: Optional[str],
) -> Dict[str, Any]:
    enriched_job_json = dict(job_json)
    source = dict(enriched_job_json.get("source") or {})
    source.setdefault("job_url", job_url)
    source["scraped_chars"] = len(raw_job_text)
    source["scraping_source"] = scraping_source or "unknown"

    if job_offer_structured:
        source["scrapegraph_job_offer"] = job_offer_structured
        enriched_job_json["job_offer_structured"] = job_offer_structured

    enriched_job_json["source"] = source
    return enriched_job_json


class AnalyzerPipeline:
    def __init__(self, nlp_service: NLPService, llm_service: OpenAILLMService):
        self.nlp_service = nlp_service
        self.llm_service = llm_service

    def load_cv_text(self, cv_path: str) -> str:
        log(f"Lecture du CV source depuis {cv_path}...", "INFO")
        with open(cv_path, "r", encoding="utf-8") as file:
            cv_text = file.read()
        log(f"CV chargé avec succès ({len(cv_text)} caractères).", "INFO")

        if not cv_text.strip():
            log(
                "Le CV source est vide : l'analyse continuera, mais le résultat sera limité.",
                "WARN",
            )

        return cv_text

    def run(
        self, job_url: str, cv_path: str = "/data/resume_europass.txt"
    ) -> AnalyzerArtifacts:
        cv_text = self.load_cv_text(cv_path)
        raw_job_text = scrape_job_offer(job_url)
        job_offer_structured = scrape_job_offer_structured(job_url)
        scraping_source = "scrapegraph" if job_offer_structured else "fallback_html"
        nlp_result = self.nlp_service.clean(raw_job_text)

        fallback_reason = None

        if not self.llm_service.is_available():
            fallback_reason = "OPENAI_API_KEY absente."
            log(
                "OPENAI_API_KEY absente : bascule en mode fallback pour produire malgré tout `job_data.json`.",
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
                openai_model=self.llm_service.current_model_id(),
            )
        else:
            try:
                cv_analysis = self.llm_service.analyze_cv(cv_text)
                job_json = self.llm_service.create_job_json(
                    job_url, raw_job_text, nlp_result, cv_analysis
                )
            except Exception as llm_error:
                fallback_reason = str(llm_error)
                log(
                    f"Échec de l'analyse LLM OpenAI, bascule en mode fallback pour générer `job_data.json` : {fallback_reason}",
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
                    openai_model=self.llm_service.current_model_id(),
                )

        job_json = enrich_job_json_with_scraping_metadata(
            job_json=job_json,
            job_url=job_url,
            raw_job_text=raw_job_text,
            job_offer_structured=job_offer_structured,
            scraping_source=scraping_source,
        )

        return AnalyzerArtifacts(
            job_url=job_url,
            cv_text=cv_text,
            raw_job_text=raw_job_text,
            nlp_result=nlp_result,
            cv_analysis=cv_analysis,
            job_json=job_json,
            fallback_reason=fallback_reason,
            job_offer_structured=job_offer_structured,
            scraping_source=scraping_source,
        )

    def write_output(
        self, job_json: Dict[str, Any], output_path: str = "/output/job_data.json"
    ) -> None:
        log(f"Écriture du fichier d'analyse final dans {output_path}...", "INFO")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(job_json, file, ensure_ascii=False, indent=2)


def create_default_pipeline() -> AnalyzerPipeline:
    return AnalyzerPipeline(
        nlp_service=NLPService(),
        llm_service=OpenAILLMService(),
    )
