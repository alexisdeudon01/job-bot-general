from __future__ import annotations

import os
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup

from analyzer.utils.logging import log

try:
    from scrapegraph_py import Client
except ImportError:  # pragma: no cover - dependency may be unavailable in some environments
    Client = None  # type: ignore[assignment]


SCRAPEGRAPH_JOB_OFFER_SCHEMA: Dict[str, Any] = {
    "job_title": "string",
    "company_name": "string",
    "location": "string",
    "employment_type": "string",
    "seniority_level": "string",
    "salary": "string",
    "remote_policy": "string",
    "recruiter_name": "string",
    "application_url": "string",
    "posted_at": "string",
    "technologies": ["string"],
    "responsibilities": ["string"],
    "requirements": ["string"],
    "benefits": ["string"],
    "languages": ["string"],
    "summary": "string",
}


def _scrape_job_offer_html(url: str, max_chars: int = 30000) -> str:
    log(f"Démarrage du scraping HTML fallback de l'offre depuis l'URL : {url}", "INFO")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=20)
    log(f"Réponse HTTP reçue avec le statut {response.status_code}", "INFO")
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()

    extracted_text = soup.get_text(separator="\n", strip=True)[:max_chars]
    log(f"Scraping HTML fallback terminé, {len(extracted_text)} caractères extraits.", "INFO")
    return extracted_text


def _build_scrapegraph_prompt() -> str:
    return (
        "Extract this job offer into structured recruitment intelligence. "
        "Identify the title, company, location, contract type, seniority, salary, "
        "remote policy, recruiter/contact if visible, application link, posting date, "
        "core technologies, responsibilities, requirements, benefits, languages, and a short summary. "
        "If a field is unavailable, return an empty string or empty list."
    )


def _normalize_structured_payload(url: str, structured: dict[str, Any] | None) -> dict[str, Any]:
    payload = structured or {}
    normalized: dict[str, Any] = {}

    for key, expected in SCRAPEGRAPH_JOB_OFFER_SCHEMA.items():
        value = payload.get(key)
        if isinstance(expected, list):
            if isinstance(value, list):
                normalized[key] = [str(item).strip() for item in value if str(item).strip()]
            elif value in (None, ""):
                normalized[key] = []
            else:
                normalized[key] = [str(value).strip()]
        else:
            normalized[key] = "" if value is None else str(value).strip()

    normalized["source_url"] = url
    return normalized


def _structured_job_offer_to_text(job_offer: dict[str, Any], max_chars: int = 30000) -> str:
    sections: list[str] = []

    ordered_scalar_fields = [
        ("Intitulé du poste", "job_title"),
        ("Entreprise", "company_name"),
        ("Localisation", "location"),
        ("Type de contrat", "employment_type"),
        ("Niveau d'expérience", "seniority_level"),
        ("Salaire", "salary"),
        ("Politique télétravail", "remote_policy"),
        ("Recruteur", "recruiter_name"),
        ("Lien de candidature", "application_url"),
        ("Date de publication", "posted_at"),
        ("Résumé", "summary"),
    ]
    ordered_list_fields = [
        ("Technologies", "technologies"),
        ("Responsabilités", "responsibilities"),
        ("Exigences", "requirements"),
        ("Avantages", "benefits"),
        ("Langues", "languages"),
    ]

    for label, key in ordered_scalar_fields:
        value = str(job_offer.get(key, "") or "").strip()
        if value:
            sections.append(f"{label}: {value}")

    for label, key in ordered_list_fields:
        values = job_offer.get(key) or []
        if isinstance(values, list):
            cleaned_values = [str(item).strip() for item in values if str(item).strip()]
            if cleaned_values:
                bullet_list = "\n".join(f"- {item}" for item in cleaned_values)
                sections.append(f"{label}:\n{bullet_list}")

    text = "\n\n".join(sections).strip()
    return text[:max_chars]


class AnalyzerScrapeGraphClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("SGAI_API_KEY")
        if not self._api_key:
            raise ValueError("Missing ScrapeGraph API key. Set the SGAI_API_KEY environment variable.")
        if Client is None:
            raise ImportError("scrapegraph-py is not installed.")
        self._client = Client(api_key=self._api_key)

    def extract_job_offer(self, url: str) -> dict[str, Any]:
        result = self._client.smartscraper(
            website_url=url,
            user_prompt=_build_scrapegraph_prompt(),
            output_schema=SCRAPEGRAPH_JOB_OFFER_SCHEMA,
        )
        if not isinstance(result, dict):
            raise ValueError("Unexpected ScrapeGraph response format for smartscraper.")
        return _normalize_structured_payload(url, result)

    def markdownify_job_page(self, url: str, max_chars: int = 30000) -> str:
        result = self._client.markdownify(website_url=url)
        markdown = result if isinstance(result, str) else str(result)
        return markdown.strip()[:max_chars]


def scrape_job_offer_structured(url: str) -> dict[str, Any]:
    log(f"Tentative d'extraction structurée via ScrapeGraph pour {url}", "INFO")
    client = AnalyzerScrapeGraphClient()
    structured = client.extract_job_offer(url)
    log("Extraction structurée ScrapeGraph terminée avec succès.", "INFO")
    return structured


def scrape_job_offer_bundle(url: str, max_chars: int = 30000) -> dict[str, Any]:
    try:
        structured = scrape_job_offer_structured(url)
        text = _structured_job_offer_to_text(structured, max_chars=max_chars)

        if not text:
            log("Le texte dérivé de la structure ScrapeGraph est vide, tentative markdownify.", "WARN")
            client = AnalyzerScrapeGraphClient()
            text = client.markdownify_job_page(url, max_chars=max_chars)

        if not text:
            raise ValueError("ScrapeGraph n'a produit aucun texte exploitable.")

        return {
            "text": text,
            "structured": structured,
            "source": "scrapegraph",
        }
    except Exception as exc:
        log(f"ScrapeGraph indisponible ou en échec, fallback HTML activé : {exc}", "WARN")
        fallback_text = _scrape_job_offer_html(url, max_chars=max_chars)
        return {
            "text": fallback_text,
            "structured": {},
            "source": "fallback_html",
            "error": str(exc),
        }


def scrape_job_offer(url: str, max_chars: int = 30000) -> str:
    bundle = scrape_job_offer_bundle(url, max_chars=max_chars)
    log(
        f"Scraping terminé via la source {bundle['source']}, {len(bundle['text'])} caractères de texte exploitable extraits.",
        "INFO",
    )
    return bundle["text"]