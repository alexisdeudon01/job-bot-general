from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Protocol, runtime_checkable

from mcp_host.clients.scrapegraph_client import ScrapegraphMCPClient
from app.services.openai_agents_service import MCPServerConfig, OpenAIAgentsService


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """Minimal protocol for plain OpenAI text/structured operations."""

    @property
    def is_configured(self) -> bool: ...

    def describe_capabilities(self) -> dict[str, Any]: ...

    def build_routing_prompt_plan(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: dict[str, Any] | None = None,
        candidate_tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    def generate_text(
        self,
        *,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def extract_structured(
        self,
        *,
        content: str,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def normalize_payload(
        self,
        *,
        payload: Any,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@dataclass(slots=True)
class ToolRecommendation:
    provider: str
    action: str
    confidence: float
    reason: str
    communication: dict[str, Any]


@dataclass(slots=True)
class ExecutionPlan:
    question: str
    recommendation: ToolRecommendation
    steps: list[dict[str, Any]]
    context: dict[str, Any]


@dataclass(slots=True)
class OrchestrationResult:
    source: dict[str, Any]
    stages: list[dict[str, Any]]
    result: dict[str, Any]


_SCRAPE_KEYWORDS = frozenset([
    "url", "website", "web page", "webpage", "page",
    "job offer", "job posting", "career page", "company page",
    "linkedin", "scrape", "extract from", "research company",
    "search the web", "find sources", "markdown",
])


def _is_provider_ready(service: Any) -> bool:
    return service is not None and bool(getattr(service, "is_configured", False))


class OrchestrationPlanner:
    """Builds a lightweight plan before execution."""

    def __init__(
        self,
        openai_service: LLMServiceProtocol | None = None,
        openai_agents_service: OpenAIAgentsService | None = None,
    ) -> None:
        self.openai_service = openai_service
        self.openai_agents_service = openai_agents_service

    def _select_provider(self, *, prefer_mcp: bool) -> str:
        if prefer_mcp and _is_provider_ready(self.openai_agents_service):
            return "openai_agents"
        if _is_provider_ready(self.openai_service):
            return "openai"
        if _is_provider_ready(self.openai_agents_service):
            return "openai_agents"
        return "openai"

    def plan(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: dict[str, Any] | None = None,
        candidate_tools: list[dict[str, Any]] | None = None,
    ) -> ExecutionPlan:
        needs_scraping = any(kw in question.lower() for kw in _SCRAPE_KEYWORDS)
        provider = self._select_provider(prefer_mcp=needs_scraping)

        if needs_scraping:
            action, confidence, reason = (
                "scrape_and_extract", 0.9,
                "Question references a URL or web resource — routing to MCP scraping tools.",
            )
        else:
            action, confidence, reason = (
                "generate_text", 0.8,
                "Plain language generation task — routing to OpenAI.",
            )

        return ExecutionPlan(
            question=question,
            recommendation=ToolRecommendation(
                provider=provider,
                action=action,
                confidence=confidence,
                reason=reason,
                communication={"question": question, "preferred_operation": preferred_operation or action},
            ),
            steps=[
                {"step": "plan", "provider": provider, "action": action},
                {"step": "execute", "provider": provider},
            ],
            context=context or {},
        )


class OrchestrationService:
    """
    OpenAI-first orchestration service.

    Routes plain LLM tasks to OpenAIService and MCP/tool tasks to OpenAIAgentsService.
    """

    def __init__(
        self,
        openai_service: LLMServiceProtocol | None = None,
        openai_agents_service: OpenAIAgentsService | None = None,
    ) -> None:
        self.openai_service = openai_service
        self.openai_agents_service = openai_agents_service
        self.planner = OrchestrationPlanner(
            openai_service=openai_service,
            openai_agents_service=openai_agents_service,
        )

    @cached_property
    def _stdio_client(self) -> ScrapegraphMCPClient:
        return ScrapegraphMCPClient()

    def describe_routing_capabilities(self) -> dict[str, Any]:
        openai_caps = self.openai_service.describe_capabilities() if self.openai_service else {}
        agents_caps = (
            self.openai_agents_service.get_capability_descriptors()
            if self.openai_agents_service else []
        )
        mcp_servers = (
            self.openai_agents_service.describe_mcp_servers()
            if self.openai_agents_service else []
        )
        return {
            "providers": {
                "openai": _provider_info(self.openai_service, "openai"),
                "openai_agents": _provider_info(self.openai_agents_service, "openai_agents"),
            },
            "capabilities": ([openai_caps] if openai_caps else []) + agents_caps,
            "mcp_servers": mcp_servers,
            "api": {
                "transport": "openai_agents_sdk",
                "mcp_transports_supported": ["stdio", "sse", "streamable_http"],
                "detail": "MCP tools are executed via OpenAI Agents SDK with full transport support.",
            },
        }

    def orchestrate(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: dict[str, Any] | None = None,
        mcp_server_configs: list[MCPServerConfig] | None = None,
    ) -> OrchestrationResult:
        plan = self.planner.plan(question=question, preferred_operation=preferred_operation, context=context)
        rec = plan.recommendation
        stages: list[dict[str, Any]] = [
            {"stage": "plan", "result": {"provider": rec.provider, "action": rec.action, "reason": rec.reason}}
        ]
        result: dict[str, Any] = {}

        try:
            if rec.provider == "openai_agents" and _is_provider_ready(self.openai_agents_service):
                result = self.openai_agents_service.run_agent(  # type: ignore[union-attr]
                    prompt=question, mcp_server_configs=mcp_server_configs
                )
                stages.append({"stage": "execute", "provider": "openai_agents", "status": "success"})
            elif _is_provider_ready(self.openai_service):
                result = self.openai_service.generate_text(prompt=question)  # type: ignore[union-attr]
                stages.append({"stage": "execute", "provider": "openai", "status": "success"})
            else:
                result = {"error": "No configured LLM provider available."}
                stages.append({"stage": "execute", "status": "error", "detail": "no_provider"})
        except Exception as exc:
            result = {"error": str(exc)}
            stages.append({"stage": "execute", "status": "error", "detail": str(exc)})

        return OrchestrationResult(
            source={"question": question, "provider": rec.provider},
            stages=stages,
            result=result,
        )

    def scrape_and_extract(
        self,
        *,
        url: str,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
        use_agents_sdk: bool = True,
    ) -> dict[str, Any]:
        if use_agents_sdk and _is_provider_ready(self.openai_agents_service):
            agent_prompt = f"Scrape the following URL and extract structured information.\nURL: {url}\nTask: {prompt}"
            if output_schema:
                agent_prompt += f"\nExpected schema: {json.dumps(output_schema)}"
            return self.openai_agents_service.run_agent(prompt=agent_prompt)  # type: ignore[union-attr]
        return asyncio.run(self._stdio_client.call_tool(
            "smartscraper",
            {"website_url": url, "user_prompt": prompt, "output_schema": output_schema},
        ))

    def markdownify(self, *, url: str, use_agents_sdk: bool = True) -> dict[str, Any]:
        if use_agents_sdk and _is_provider_ready(self.openai_agents_service):
            return self.openai_agents_service.run_agent(  # type: ignore[union-attr]
                prompt=f"Convert the following URL to clean markdown format.\nURL: {url}"
            )
        return asyncio.run(self._stdio_client.call_tool("markdownify", {"website_url": url}))


def _provider_info(service: Any, name: str) -> dict[str, Any]:
    if service is None:
        return {"available": False, "provider": name}
    return {
        "available": getattr(service, "is_configured", False),
        "provider": name,
        "model": getattr(service, "default_model", None),
    }
