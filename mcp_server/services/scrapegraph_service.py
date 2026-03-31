from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from typing import Any

from scrapegraph_py import Client

from mcp_server.utils.errors import MCPServerError


class ScrapeGraphConfigurationError(MCPServerError):
    """Raised when ScrapeGraph configuration is missing or invalid."""


class ScrapeGraphRequestError(MCPServerError):
    """Raised when a ScrapeGraph SDK call fails."""


@dataclass(frozen=True)
class ScrapeGraphToolDefinition:
    name: str
    purpose: str
    accepts_url: bool = False
    accepts_prompt: bool = False
    supports_schema: bool = False


@dataclass(frozen=True)
class ScrapeGraphPreparedCall:
    tool_name: str
    user_question: str
    communication_prompt: str | None
    payload: dict[str, Any]
    rationale: str


class ScrapeGraphToolPlanner:
    """Upper-layer helper to prepare prompts and payloads for ScrapeGraph tools."""

    OFFICIAL_TOOL_DEFINITIONS: tuple[ScrapeGraphToolDefinition, ...] = (
        ScrapeGraphToolDefinition(
            name="markdownify",
            purpose="Transform a web page into markdown for downstream reading or extraction.",
            accepts_url=True,
        ),
        ScrapeGraphToolDefinition(
            name="smartscraper",
            purpose="Extract structured information from a single web page using a natural-language prompt.",
            accepts_url=True,
            accepts_prompt=True,
            supports_schema=True,
        ),
        ScrapeGraphToolDefinition(
            name="searchscraper",
            purpose="Search across the web and extract focused information from multiple results.",
            accepts_prompt=True,
            supports_schema=True,
        ),
        ScrapeGraphToolDefinition(
            name="scrape",
            purpose="Fetch raw page content with rendering options when available.",
            accepts_url=True,
        ),
        ScrapeGraphToolDefinition(
            name="sitemap",
            purpose="List sitemap URLs and website structure.",
            accepts_url=True,
        ),
        ScrapeGraphToolDefinition(
            name="smartcrawler_initiate",
            purpose="Launch an asynchronous multi-page crawl.",
            accepts_url=True,
            accepts_prompt=True,
        ),
        ScrapeGraphToolDefinition(
            name="smartcrawler_fetch_results",
            purpose="Fetch results for a previously started crawl.",
        ),
        ScrapeGraphToolDefinition(
            name="agentic_scrapper",
            purpose="Run advanced agentic scraping workflows with optional steps and schema.",
            accepts_url=True,
            accepts_prompt=True,
            supports_schema=True,
        ),
    )

    def list_tool_definitions(self) -> list[ScrapeGraphToolDefinition]:
        return list(self.OFFICIAL_TOOL_DEFINITIONS)

    def get_tool_definition(self, tool_name: str) -> ScrapeGraphToolDefinition:
        for definition in self.OFFICIAL_TOOL_DEFINITIONS:
            if definition.name == tool_name:
                return definition
        raise ValueError(f"Unknown ScrapeGraph tool: {tool_name}")

    def prepare_call(
        self,
        tool_name: str,
        question: str,
        *,
        url: str | None = None,
        output_schema: dict[str, Any] | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> ScrapeGraphPreparedCall:
        definition = self.get_tool_definition(tool_name)
        payload = dict(extra_payload or {})
        communication_prompt = self._build_communication_prompt(
            tool_name=tool_name,
            question=question,
            output_schema=output_schema,
        )

        if definition.accepts_url and url:
            payload.setdefault("website_url", url)
            if tool_name in {"smartcrawler_initiate", "agentic_scrapper"}:
                payload.setdefault("url", url)

        if definition.accepts_prompt and communication_prompt:
            if tool_name == "searchscraper":
                payload.setdefault("user_prompt", communication_prompt)
            elif tool_name == "smartscraper":
                payload.setdefault("user_prompt", communication_prompt)
            elif tool_name == "smartcrawler_initiate":
                payload.setdefault("prompt", communication_prompt)
            elif tool_name == "agentic_scrapper":
                payload.setdefault("user_prompt", communication_prompt)

        if definition.supports_schema and output_schema is not None:
            payload.setdefault("output_schema", output_schema)

        if tool_name == "markdownify" and url:
            payload = {"website_url": url, **payload}
        elif tool_name == "scrape" and url:
            payload.setdefault("website_url", url)
        elif tool_name == "sitemap" and url:
            payload.setdefault("website_url", url)

        return ScrapeGraphPreparedCall(
            tool_name=tool_name,
            user_question=question,
            communication_prompt=communication_prompt,
            payload=payload,
            rationale=self._build_rationale(tool_name, question, url=url, output_schema=output_schema),
        )

    def build_server_command(
        self,
        *,
        module: str = "mcp_server",
        host: str | None = None,
        port: int | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        command = ["python", "-m", module]
        if host:
            command.extend(["--host", host])
        if port is not None:
            command.extend(["--port", str(port)])
        if extra_args:
            command.extend(extra_args)
        return command

    def build_server_command_string(
        self,
        *,
        module: str = "mcp_server",
        host: str | None = None,
        port: int | None = None,
        extra_args: list[str] | None = None,
    ) -> str:
        return " ".join(
            shlex.quote(part)
            for part in self.build_server_command(
                module=module,
                host=host,
                port=port,
                extra_args=extra_args,
            )
        )

    def _build_communication_prompt(
        self,
        *,
        tool_name: str,
        question: str,
        output_schema: dict[str, Any] | None = None,
    ) -> str | None:
        if tool_name == "markdownify":
            return None

        prompt = question.strip()
        if not prompt:
            return None

        if output_schema:
            return (
                f"{prompt} Return only the requested information aligned with the provided schema. "
                "If some fields are not available, omit them or leave them empty."
            )

        if tool_name in {"smartscraper", "searchscraper", "agentic_scrapper", "smartcrawler_initiate"}:
            return (
                f"{prompt} Keep the result concise, factual, and adaptive to the available source content. "
                "Do not invent missing details."
            )

        return prompt

    def _build_rationale(
        self,
        tool_name: str,
        question: str,
        *,
        url: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> str:
        target = f" on {url}" if url else ""
        schema_note = " with caller-provided schema" if output_schema else ""
        return f"Use ScrapeGraph tool '{tool_name}' to address: {question}{target}{schema_note}."


class ScrapeGraphService:
    AVAILABLE_TOOLS: tuple[str, ...] = tuple(
        definition.name for definition in ScrapeGraphToolPlanner.OFFICIAL_TOOL_DEFINITIONS
    )

    def __init__(
        self,
        api_key: str | None = None,
        planner: ScrapeGraphToolPlanner | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("SGAI_API_KEY")
        if not resolved_api_key:
            raise ScrapeGraphConfigurationError(
                "Missing ScrapeGraph API key. Set the SGAI_API_KEY environment variable."
            )
        self._client = Client(api_key=resolved_api_key)
        self._planner = planner or ScrapeGraphToolPlanner()

    def list_available_tools(self) -> list[str]:
        return list(self.AVAILABLE_TOOLS)

    def list_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "purpose": definition.purpose,
                "accepts_url": definition.accepts_url,
                "accepts_prompt": definition.accepts_prompt,
                "supports_schema": definition.supports_schema,
            }
            for definition in self._planner.list_tool_definitions()
        ]

    def prepare_tool_call(
        self,
        tool_name: str,
        question: str,
        *,
        url: str | None = None,
        output_schema: dict[str, Any] | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prepared = self._planner.prepare_call(
            tool_name=tool_name,
            question=question,
            url=url,
            output_schema=output_schema,
            extra_payload=extra_payload,
        )
        return {
            "tool_name": prepared.tool_name,
            "user_question": prepared.user_question,
            "communication_prompt": prepared.communication_prompt,
            "payload": prepared.payload,
            "rationale": prepared.rationale,
        }

    def build_server_command(
        self,
        *,
        module: str = "mcp_server",
        host: str | None = None,
        port: int | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        return self._planner.build_server_command(
            module=module,
            host=host,
            port=port,
            extra_args=extra_args,
        )

    def build_server_command_string(
        self,
        *,
        module: str = "mcp_server",
        host: str | None = None,
        port: int | None = None,
        extra_args: list[str] | None = None,
    ) -> str:
        return self._planner.build_server_command_string(
            module=module,
            host=host,
            port=port,
            extra_args=extra_args,
        )

    def extract(
        self,
        url: str,
        user_prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._call_smartscraper(url, user_prompt, output_schema)

    def search_extract(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call_searchscraper(payload)

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
        return self.extract(url=url, user_prompt=prompt, output_schema=schema)

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
        return self.search_extract(payload)

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
                output_schema=output_schema,  # type: ignore[arg-type]
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