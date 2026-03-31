from __future__ import annotations

from typing import Any

from mcp_server.clients.orchestrator_client import OrchestratorClient
from mcp_server.services.normalization import (
    build_generate_payload,
    build_run_payload,
    normalize_analyze_result,
    validate_job_url,
)
from mcp_server.services.scrapegraph_service import ScrapeGraphService
from mcp_server.utils.errors import MCPServerError


def error_to_dict(error: Exception) -> dict[str, str]:
    return {"error": str(error)}


def _compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        compacted[key] = value
    return compacted


def register_tools(mcp, client: OrchestratorClient) -> None:
    scrapegraph_service: ScrapeGraphService | None = None

    def get_scrapegraph_service() -> ScrapeGraphService:
        nonlocal scrapegraph_service
        if scrapegraph_service is None:
            scrapegraph_service = ScrapeGraphService()
        return scrapegraph_service

    @mcp.tool()
    def analyze_job(url: str) -> dict:
        """Analyze a job offer URL and return structured information from the orchestrator."""
        try:
            valid_url = validate_job_url(url)
            response = client.post("/api/analyze", {"url": valid_url})
            return normalize_analyze_result(response)
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def generate_documents(job_data: dict, resume_text: str | None = None) -> dict:
        """Generate provider-backed application documents from structured job data."""
        try:
            payload = build_generate_payload(job_data, resume_text)
            return client.post("/api/generate", payload)
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def run_full_pipeline(url: str, resume_text: str | None = None) -> dict:
        """Run the orchestrator pipeline for acquisition, extraction, and generation."""
        try:
            payload = build_run_payload(url, resume_text)
            return client.post("/api/run", payload)
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def scrapegraph_extract(url: str, prompt: str, schema: dict[str, Any] | None = None) -> dict:
        """Extract structured information from a web page using ScrapeGraph and an optional caller-provided schema."""
        try:
            valid_url = validate_job_url(url)
            cleaned_prompt = prompt.strip() if isinstance(prompt, str) else ""
            if not cleaned_prompt:
                raise MCPServerError("prompt must be a non-empty string")
            return get_scrapegraph_service()._call_smartscraper(
                url=valid_url,
                user_prompt=cleaned_prompt,
                output_schema=schema,
            )
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def scrapegraph_extract_job_offer(url: str) -> dict:
        """Extract a structured job offer from a URL using ScrapeGraph's job-oriented helper."""
        try:
            valid_url = validate_job_url(url)
            return get_scrapegraph_service().extract_job_offer(valid_url)
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def scrapegraph_company_hiring_intelligence(
        company_name: str,
        role_focus: str | None = None,
        location: str | None = None,
        num_results: int = 5,
        time_range: str = "30d",
    ) -> dict:
        """Research company hiring and market signals with ScrapeGraph search."""
        try:
            if not company_name or not isinstance(company_name, str):
                raise MCPServerError("company_name must be a non-empty string")
            return get_scrapegraph_service().research_company_hiring_signals(
                company_name=company_name,
                role_focus=role_focus,
                location=location,
                num_results=num_results,
                time_range=time_range,
            )
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def scrapegraph_markdownify(url: str) -> dict:
        """Convert a page into markdown for downstream analysis or prompting."""
        try:
            valid_url = validate_job_url(url)
            return get_scrapegraph_service().markdownify_job_page(valid_url)
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def infer_entities(
        text: str | None = None,
        document: dict[str, Any] | None = None,
        entity_types: list[str] | None = None,
    ) -> dict:
        """Infer candidate entities from free text or a structured document without using hardcoded fake results."""
        try:
            source_fragments: list[str] = []
            if isinstance(text, str) and text.strip():
                source_fragments.append(text.strip())
            if isinstance(document, dict) and document:
                source_fragments.extend(
                    str(value).strip()
                    for value in document.values()
                    if isinstance(value, str) and value.strip()
                )

            if not source_fragments:
                raise MCPServerError("Provide non-empty text or a document with textual fields")

            tokens: list[str] = []
            seen: set[str] = set()
            for fragment in source_fragments:
                for raw_token in fragment.replace("/", " ").replace(",", " ").split():
                    token = raw_token.strip("()[]{}<>.:;!?\"'")
                    if len(token) < 3:
                        continue
                    if not any(character.isalpha() for character in token):
                        continue
                    normalized = token.lower()
                    if normalized in seen:
                        continue
                    seen.add(normalized)
                    tokens.append(token)
                    if len(tokens) >= 50:
                        break
                if len(tokens) >= 50:
                    break

            inferred_type = "entity"
            if entity_types:
                filtered_types = [item.strip() for item in entity_types if isinstance(item, str) and item.strip()]
                if filtered_types:
                    inferred_type = filtered_types[0]

            entities = [{"name": token, "type": inferred_type} for token in tokens]
            return _compact_dict(
                {
                    "entity_types": entity_types,
                    "entity_count": len(entities),
                    "entities": entities,
                }
            )
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def enrich_entities(
        entities: list[dict[str, Any]],
        role_focus: str | None = None,
        location: str | None = None,
        num_results: int = 5,
        time_range: str = "30d",
    ) -> dict:
        """Enrich structured entities with provider-backed web research where a company-like entity is available."""
        try:
            if not isinstance(entities, list) or not entities:
                raise MCPServerError("entities must be a non-empty list")

            company_name: str | None = None
            passthrough_entities: list[dict[str, Any]] = []

            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                passthrough_entities.append(_compact_dict(entity))
                entity_name = entity.get("name")
                entity_type = str(entity.get("type", "")).lower()
                if (
                    company_name is None
                    and isinstance(entity_name, str)
                    and entity_name.strip()
                    and entity_type in {"company", "organization", "employer"}
                ):
                    company_name = entity_name.strip()

            result: dict[str, Any] = {"entities": passthrough_entities}

            if company_name:
                result["research"] = get_scrapegraph_service().research_company_hiring_signals(
                    company_name=company_name,
                    role_focus=role_focus,
                    location=location,
                    num_results=num_results,
                    time_range=time_range,
                )
            else:
                result["note"] = (
                    "No company-like entity found. Returned validated entities without external enrichment."
                )

            return _compact_dict(result)
        except MCPServerError as exc:
            return error_to_dict(exc)
