from __future__ import annotations

import os
from typing import Any

from scrapegraph_py import Client

from mcp_server.utils.errors import MCPServerError


class ScrapeGraphConfigurationError(MCPServerError):
    """Raised when ScrapeGraph configuration is missing or invalid."""


class ScrapeGraphRequestError(MCPServerError):
    """Raised when a ScrapeGraph SDK call fails."""


class ScrapeGraphService:
    def __init__(self, api_key: str | None = None) -> None:
        resolved_api_key = api_key or os.getenv("SGAI_API_KEY")
        if not resolved_api_key:
            raise ScrapeGraphConfigurationError(
                "Missing ScrapeGraph API key. Set the SGAI_API_KEY environment variable."
            )
        self._client = Client(api_key=resolved_api_key)

    def extract_job_offer(self, url: str) -> dict[str, Any]:
        schema = {
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
        prompt = (
            "Extract this job offer into structured recruitment intelligence. "
            "Identify the title, company, location, contract type, seniority, salary, "
            "remote policy, recruiter/contact if visible, application link, posting date, "
            "core technologies, responsibilities, requirements, benefits, languages, and a short summary. "
            "If a field is unavailable, return an empty string or empty list."
        )
        return self._call_smartscraper(url, prompt, schema)

    def research_company_hiring_signals(
        self,
        company_name: str,
        role_focus: str | None = None,
        location: str | None = None,
        num_results: int = 5,
        time_range: str = "30d",
    ) -> dict[str, Any]:
        prompt_parts = [
            f"Research the company {company_name} for job-search intelligence.",
            "Find recent hiring signals, official careers pages, recent news, funding or product updates,",
            "employer brand indicators, interview/process insights if available, and technologies mentioned across sources.",
            "Return concise, recruiter- and candidate-useful information.",
        ]
        if role_focus:
            prompt_parts.append(f"Prioritize information relevant to {role_focus}.")
        if location:
            prompt_parts.append(f"Focus on opportunities or signals related to {location}.")
        schema = {
            "company_name": "string",
            "company_summary": "string",
            "hiring_signals": ["string"],
            "recent_news": ["string"],
            "open_roles_signals": ["string"],
            "tech_stack_signals": ["string"],
            "candidate_angle": ["string"],
            "sources": ["string"],
        }
        payload: dict[str, Any] = {
            "user_prompt": " ".join(prompt_parts),
            "num_results": num_results,
            "extraction_mode": "markdown",
            "output_schema": schema,
            "time_range": time_range,
        }
        if location:
            payload["location_geo_code"] = location
        return self._call_searchscraper(payload)

    def markdownify_job_page(self, url: str) -> dict[str, Any]:
        try:
            result = self._client.markdownify(website_url=url)
            return {"url": url, "markdown": result}
        except Exception as exc:
            raise ScrapeGraphRequestError(f"ScrapeGraph markdownify failed: {exc}") from exc

    def _call_smartscraper(
        self,
        url: str,
        user_prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            result = self._client.smartscraper(
                website_url=url,
                user_prompt=user_prompt,
                output_schema=output_schema,
            )
            return {"url": url, "result": result}
        except Exception as exc:
            raise ScrapeGraphRequestError(f"ScrapeGraph smartscraper failed: {exc}") from exc

    def _call_searchscraper(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self._client.searchscraper(**payload)
            return {"query": payload["user_prompt"], "result": result}
        except Exception as exc:
            raise ScrapeGraphRequestError(f"ScrapeGraph searchscraper failed: {exc}") from exc