from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from mcp_server.clients.orchestrator_client import OrchestratorClient
from mcp_server.clients.scrapegraph_stdio_client import ScrapeGraphStdioClient
from mcp_server.services.scrapegraph_service import ScrapeGraphService
from app.services.openai_agents_service import MCPServerConfig, OpenAIAgentsService


class LLMServiceProtocol:
    """Minimal protocol for plain OpenAI text/structured operations."""

    @property
    def is_configured(self) -> bool:
        return False

    def get_capability_descriptors(self) -> list[dict[str, Any]]:
        return []

    def describe_capabilities(self) -> dict[str, Any]:
        return {}

    def build_routing_prompt_plan(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: dict[str, Any] | None = None,
        candidate_tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {}

    def generate_text(
        self,
        *,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {}

    def extract_structured(
        self,
        *,
        content: str,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {}

    def normalize_payload(
        self,
        *,
        payload: Any,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {}


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


class OrchestrationPlanner:
    """Builds a lightweight plan before execution."""

    SCRAPE_KEYWORDS = (
        "url",
        "website",
        "web page",
        "webpage",
        "page",
        "job offer",
        "job posting",
        "career page",
        "company page",
        "linkedin",
        "scrape",
        "extract from",
        "research company",
        "search the web",
        "find sources",
        "markdown",
    )

    def __init__(
        self,
        openai_service: LLMServiceProtocol | None = None,
        openai_agents_service: OpenAIAgentsService | None = None,
    ) -> None:
        self.openai_service = openai_service
        self.openai_agents_service = openai_agents_service

    def _is_provider_ready(self, service: Any) -> bool:
        if service is None:
            return False
        return bool(getattr(service, "is_configured", False))

    def _select_llm_provider(
        self,
        *,
        prefer_provider: str | None = None,
        prefer_mcp: bool = False,
    ) -> str:
        """Select the best available provider. Always OpenAI-first."""
        if prefer_mcp and self._is_provider_ready(self.openai_agents_service):
            return "openai_agents"
        if self._is_provider_ready(self.openai_service):
            return "openai"
        if self._is_provider_ready(self.openai_agents_service):
            return "openai_agents"
        return "openai"

    def _question_needs_scraping(self, question: str) -> bool:
        lowered = question.lower()
        return any(kw in lowered for kw in self.SCRAPE_KEYWORDS)

    def _is_valid_url(self, text: str) -> bool:
        try:
            result = urlparse(text.strip())
            return result.scheme in ("http", "https") and bool(result.netloc)
        except Exception:
            return False

    def plan(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: dict[str, Any] | None = None,
        candidate_tools: list[dict[str, Any]] | None = None,
    ) -> ExecutionPlan:
        needs_scraping = self._question_needs_scraping(question)
        provider = self._select_llm_provider(prefer_mcp=needs_scraping)

        if needs_scraping:
            action = "scrape_and_extract"
            confidence = 0.9
            reason = "Question references a URL or web resource — routing to MCP scraping tools."
        else:
            action = "generate_text"
            confidence = 0.8
            reason = "Plain language generation task — routing to OpenAI."

        recommendation = ToolRecommendation(
            provider=provider,
            action=action,
            confidence=confidence,
            reason=reason,
            communication={
                "question": question,
                "preferred_operation": preferred_operation or action,
            },
        )
        steps: list[dict[str, Any]] = [
            {"step": "plan", "provider": provider, "action": action},
            {"step": "execute", "provider": provider},
        ]
        return ExecutionPlan(
            question=question,
            recommendation=recommendation,
            steps=steps,
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
        self._scrapegraph_service: ScrapeGraphService | None = None
        self._stdio_client: ScrapeGraphStdioClient | None = None

    def _get_scrapegraph_service(self) -> ScrapeGraphService:
        if self._scrapegraph_service is None:
            self._scrapegraph_service = ScrapeGraphService()
        return self._scrapegraph_service

    def _get_stdio_client(self) -> ScrapeGraphStdioClient:
        if self._stdio_client is None:
            self._stdio_client = ScrapeGraphStdioClient(self._get_scrapegraph_service())
        return self._stdio_client

    def describe_routing_capabilities(self) -> dict[str, Any]:
        openai_caps = (
            self.openai_service.get_capability_descriptors()
            if self.openai_service
            else []
        )
        agents_caps = (
            self.openai_agents_service.get_capability_descriptors()
            if self.openai_agents_service
            else []
        )
        mcp_servers = (
            self.openai_agents_service.describe_mcp_servers()
            if self.openai_agents_service
            else []
        )
        return {
            "providers": {
                "openai": self._provider_capabilities(self.openai_service, "openai"),
                "openai_agents": self._provider_capabilities(
                    self.openai_agents_service, "openai_agents"
                ),
            },
            "capabilities": openai_caps + agents_caps,
            "mcp_servers": mcp_servers,
            "api": {
                "transport": "openai_agents_sdk",
                "mcp_transports_supported": ["stdio", "sse", "streamable_http"],
                "detail": "MCP tools are executed via OpenAI Agents SDK with full transport support.",
            },
        }

    def _provider_capabilities(
        self, service: Any, provider_name: str
    ) -> dict[str, Any]:
        if service is None:
            return {"available": False, "provider": provider_name}
        return {
            "available": getattr(service, "is_configured", False),
            "provider": provider_name,
            "model": getattr(service, "default_model", None),
        }

    def _resolve_provider_chain(self) -> list[tuple[str, Any]]:
        """Return ordered list of (name, service) for available providers."""
        chain: list[tuple[str, Any]] = []
        if self.openai_service and getattr(self.openai_service, "is_configured", False):
            chain.append(("openai", self.openai_service))
        if self.openai_agents_service and getattr(
            self.openai_agents_service, "is_configured", False
        ):
            chain.append(("openai_agents", self.openai_agents_service))
        return chain

    def _is_provider_ready(self, service: Any) -> bool:
        if service is None:
            return False
        return bool(getattr(service, "is_configured", False))

    # ------------------------------------------------------------------
    # Orchestration entry points
    # ------------------------------------------------------------------

    def orchestrate(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: dict[str, Any] | None = None,
        mcp_server_configs: list[MCPServerConfig] | None = None,
    ) -> OrchestrationResult:
        """
        Main orchestration entry point.

        - MCP/scraping tasks → OpenAIAgentsService (with MCP tools)
        - Plain LLM tasks → OpenAIService (direct chat completions)
        """
        plan = self.planner.plan(
            question=question,
            preferred_operation=preferred_operation,
            context=context,
        )
        stages: list[dict[str, Any]] = [
            {
                "stage": "plan",
                "result": {
                    "provider": plan.recommendation.provider,
                    "action": plan.recommendation.action,
                    "reason": plan.recommendation.reason,
                },
            }
        ]

        provider = plan.recommendation.provider
        result: dict[str, Any] = {}

        try:
            if provider == "openai_agents" and self._is_provider_ready(
                self.openai_agents_service
            ):
                assert self.openai_agents_service is not None
                agent_result = self.openai_agents_service.run_agent(
                    prompt=question,
                    mcp_server_configs=mcp_server_configs,
                )
                result = agent_result
                stages.append(
                    {
                        "stage": "execute",
                        "provider": "openai_agents",
                        "status": "success",
                    }
                )

            elif self._is_provider_ready(self.openai_service):
                assert self.openai_service is not None
                llm_result = self.openai_service.generate_text(prompt=question)
                result = llm_result
                stages.append(
                    {"stage": "execute", "provider": "openai", "status": "success"}
                )

            else:
                result = {"error": "No configured LLM provider available."}
                stages.append(
                    {"stage": "execute", "status": "error", "detail": "no_provider"}
                )

        except Exception as exc:
            result = {"error": str(exc)}
            stages.append({"stage": "execute", "status": "error", "detail": str(exc)})

        return OrchestrationResult(
            source={"question": question, "provider": provider},
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
        """
        Scrape a URL and extract structured data.

        When use_agents_sdk=True, delegates to OpenAI Agents SDK with MCP tools.
        Falls back to direct ScrapeGraphStdioClient for non-agent execution.
        """
        if use_agents_sdk and self._is_provider_ready(self.openai_agents_service):
            assert self.openai_agents_service is not None
            agent_prompt = f"Scrape the following URL and extract structured information.\nURL: {url}\nTask: {prompt}"
            if output_schema:
                agent_prompt += f"\nExpected schema: {json.dumps(output_schema)}"
            return self.openai_agents_service.run_agent(prompt=agent_prompt)

        # Direct fallback via ScrapeGraphStdioClient
        return self._get_stdio_client().call_tool(
            "smartscraper",
            {"website_url": url, "user_prompt": prompt, "output_schema": output_schema},
        )

    def markdownify(self, *, url: str, use_agents_sdk: bool = True) -> dict[str, Any]:
        """Convert a URL to markdown."""
        if use_agents_sdk and self._is_provider_ready(self.openai_agents_service):
            assert self.openai_agents_service is not None
            return self.openai_agents_service.run_agent(
                prompt=f"Convert the following URL to clean markdown format.\nURL: {url}"
            )
        return self._get_stdio_client().call_tool("markdownify", {"website_url": url})

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_sparse_dicts(*values: dict[str, Any] | None) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for value in values:
            if not value:
                continue
            for key, item in value.items():
                if item is None:
                    continue
                if isinstance(item, str) and not item.strip():
                    continue
                if isinstance(item, (list, dict)) and not item:
                    continue
                merged[key] = item
        return merged

    @staticmethod
    def _drop_absent_values(value: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if item is None:
                continue
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    continue
                cleaned[key] = stripped
                continue
            if isinstance(item, list):
                compact_list = [
                    entry for entry in item if entry not in (None, "", [], {})
                ]
                if compact_list:
                    cleaned[key] = compact_list
                continue
            if isinstance(item, dict):
                compact_dict = OrchestrationService._drop_absent_values(item)
                if compact_dict:
                    cleaned[key] = compact_dict
                continue
            cleaned[key] = item
        return cleaned

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return json.dumps(
                value, ensure_ascii=False, indent=2, sort_keys=True, default=str
            )
        return str(value)
