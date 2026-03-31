from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from mcp_server.clients.orchestrator_client import OrchestratorClient
from mcp_server.clients.scrapegraph_stdio_client import ScrapeGraphStdioClient
from mcp_server.services.scrapegraph_service import ScrapeGraphService


class LLMServiceProtocol(Protocol):
    @property
    def is_configured(self) -> bool: ...

    def get_capability_descriptors(self) -> list[dict[str, Any]]: ...

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
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def normalize_payload(
        self,
        *,
        payload: Any,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
        **kwargs: Any,
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

    API_KEYWORDS = (
        "api",
        "backend",
        "endpoint",
        "forward",
        "post to",
        "send to",
        "save to",
        "persist",
        "store in api",
    )

    STRUCTURED_KEYWORDS = (
        "extract",
        "structured",
        "json",
        "normalize",
        "schema",
        "parse",
        "fields",
    )

    def __init__(
        self,
        scrape_client: ScrapeGraphStdioClient,
        openai_service: LLMServiceProtocol | None = None,
        anthropic_service: LLMServiceProtocol | None = None,
    ) -> None:
        self.scrape_client = scrape_client
        self.openai_service = openai_service
        self.anthropic_service = anthropic_service

    def build_plan(
        self,
        *,
        question: str,
        source: dict[str, Any] | None = None,
        instructions: str | None = None,
        target_schema: dict[str, Any] | None = None,
        endpoint: str | None = None,
        payload: dict[str, Any] | None = None,
        prefer_provider: str | None = None,
        include_markdown: bool = True,
        num_results: int | None = None,
    ) -> ExecutionPlan:
        normalized_question = question.strip()
        source = source or {}
        recommendation = self._recommend_tool(
            question=normalized_question,
            source=source,
            instructions=instructions,
            target_schema=target_schema,
            endpoint=endpoint,
            payload=payload,
            prefer_provider=prefer_provider,
            include_markdown=include_markdown,
            num_results=num_results,
        )
        planning_step = {
            "stage": "planning",
            "status": "completed",
            "message": f"Voici ma question: {normalized_question}. Quel outil proposer, comment communiquer avec lui ?",
            "recommendation": self._recommendation_to_dict(recommendation),
        }
        return ExecutionPlan(
            question=normalized_question,
            recommendation=recommendation,
            steps=[planning_step],
            context={
                "source": source,
                "instructions": instructions,
                "target_schema": target_schema or {},
                "endpoint": endpoint,
                "payload": payload or {},
                "prefer_provider": prefer_provider,
                "include_markdown": include_markdown,
                "num_results": num_results,
            },
        )

    def _recommend_tool(
        self,
        *,
        question: str,
        source: dict[str, Any],
        instructions: str | None,
        target_schema: dict[str, Any] | None,
        endpoint: str | None,
        payload: dict[str, Any] | None,
        prefer_provider: str | None,
        include_markdown: bool,
        num_results: int | None,
    ) -> ToolRecommendation:
        source_type = source.get("type")
        source_value = source.get("value")
        lower_question = question.lower()

        if endpoint or (payload and self._contains_keyword(lower_question, self.API_KEYWORDS)):
            return ToolRecommendation(
                provider="api",
                action="forward_to_api",
                confidence=0.95,
                reason="The request explicitly targets a backend/API handoff.",
                communication={
                    "endpoint": endpoint,
                    "payload": payload or {},
                    "mode": "direct_post",
                },
            )

        if source_type == "url" and isinstance(source_value, str):
            communication = {
                "tool": "scrapegraph_extract",
                "arguments": {
                    "url": source_value,
                    "prompt": instructions or question,
                    "schema": target_schema,
                },
                "follow_up": {
                    "markdownify": include_markdown,
                    "provider_enrichment": self._select_llm_provider(prefer_provider, structured=True),
                },
            }
            return ToolRecommendation(
                provider="scrapegraph",
                action="extract_from_url",
                confidence=0.96,
                reason="A concrete URL is present, so web extraction should happen before any LLM enrichment.",
                communication=communication,
            )

        if source_type == "entity" and isinstance(source_value, str):
            communication = {
                "tool": "scrapegraph_search_extract",
                "arguments": {
                    "prompt": instructions or question,
                    "schema": target_schema,
                    "num_results": num_results or 5,
                },
                "follow_up": {
                    "provider_enrichment": self._select_llm_provider(prefer_provider, structured=True),
                },
            }
            return ToolRecommendation(
                provider="scrapegraph",
                action="enrich_entity",
                confidence=0.92,
                reason="Entity research benefits from web search and extraction across multiple sources.",
                communication=communication,
            )

        if self._is_probable_url(source_value) or self._contains_keyword(lower_question, self.SCRAPE_KEYWORDS):
            inferred_url = source_value if self._is_probable_url(source_value) else None
            tool_name = "scrapegraph_extract" if inferred_url else "scrapegraph_search_extract"
            arguments: dict[str, Any] = {
                "prompt": instructions or question,
                "schema": target_schema,
            }
            if inferred_url:
                arguments = {"url": inferred_url, "prompt": instructions or question, "schema": target_schema}
            else:
                arguments["num_results"] = num_results or 5

            return ToolRecommendation(
                provider="scrapegraph",
                action="auto_scrape_route",
                confidence=0.82,
                reason="The question suggests live web content acquisition or search-driven extraction.",
                communication={
                    "tool": tool_name,
                    "arguments": arguments,
                    "follow_up": {
                        "provider_enrichment": self._select_llm_provider(prefer_provider, structured=True),
                        "markdownify": include_markdown if inferred_url else False,
                    },
                },
            )

        llm_provider = self._select_llm_provider(
            prefer_provider,
            structured=bool(target_schema) or self._contains_keyword(lower_question, self.STRUCTURED_KEYWORDS),
        )
        llm_action = "extract_structured" if (target_schema or self._contains_keyword(lower_question, self.STRUCTURED_KEYWORDS)) else "generate_text"

        return ToolRecommendation(
            provider=llm_provider,
            action=llm_action,
            confidence=0.78 if llm_provider != "none" else 0.3,
            reason="The request looks like a direct language task without a clear need for web scraping or API forwarding.",
            communication={
                "instructions": instructions or question,
                "target_schema": target_schema,
                "content_source": source_type or "text",
                "preferred_provider": prefer_provider,
            },
        )

    def _select_llm_provider(self, prefer_provider: str | None, *, structured: bool) -> str:
        if prefer_provider == "openai" and self._is_provider_ready(self.openai_service):
            return "openai"
        if prefer_provider == "anthropic" and self._is_provider_ready(self.anthropic_service):
            return "anthropic"

        if structured:
            if self._is_provider_ready(self.openai_service):
                return "openai"
            if self._is_provider_ready(self.anthropic_service):
                return "anthropic"
        else:
            if self._is_provider_ready(self.anthropic_service):
                return "anthropic"
            if self._is_provider_ready(self.openai_service):
                return "openai"

        return "none"

    @staticmethod
    def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _is_provider_ready(provider: LLMServiceProtocol | None) -> bool:
        return bool(provider and getattr(provider, "is_configured", True))

    @staticmethod
    def _is_probable_url(value: Any) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False
        parsed = urlparse(value)
        return bool(parsed.scheme and parsed.netloc)

    @staticmethod
    def _recommendation_to_dict(recommendation: ToolRecommendation) -> dict[str, Any]:
        return {
            "provider": recommendation.provider,
            "action": recommendation.action,
            "confidence": recommendation.confidence,
            "reason": recommendation.reason,
            "communication": recommendation.communication,
        }


class OrchestrationService:
    """Global entrypoint that plans, routes, and executes requests across providers and tools."""

    def __init__(
        self,
        api_client: OrchestratorClient | None = None,
        scrape_client: ScrapeGraphStdioClient | None = None,
        openai_service: LLMServiceProtocol | None = None,
        anthropic_service: LLMServiceProtocol | None = None,
    ) -> None:
        self.api_client = api_client or OrchestratorClient()
        self.scrape_service = ScrapeGraphService()
        self.scrape_client = scrape_client or ScrapeGraphStdioClient(service=self.scrape_service)
        self.openai_service = openai_service
        self.anthropic_service = anthropic_service
        self.planner = OrchestrationPlanner(
            scrape_client=self.scrape_client,
            openai_service=openai_service,
            anthropic_service=anthropic_service,
        )

    def list_scrape_tools(self) -> list[dict[str, Any]]:
        return self.scrape_client.list_tools()

    def describe_routing_capabilities(self) -> dict[str, Any]:
        return {
            "scrapegraph": {
                "tools": self.scrape_service.list_tool_definitions(),
                "server_command": self.scrape_service.build_server_command_string(module="mcp_server.main"),
            },
            "openai": self._provider_capabilities(self.openai_service, "openai"),
            "anthropic": self._provider_capabilities(self.anthropic_service, "anthropic"),
            "api": {
                "operation": "forward_to_api",
                "description": "Send structured payloads to orchestrator backend endpoints.",
            },
        }

    def start_scrapegraph_server_command(self) -> str:
        return self.scrape_service.build_server_command_string(module="mcp_server.main")

    def _provider_capabilities(
        self,
        provider: LLMServiceProtocol | None,
        provider_name: str,
    ) -> dict[str, Any]:
        if provider is None:
            return {
                "provider": provider_name,
                "configured": False,
                "capabilities": [],
            }
        return self._as_dict(provider.describe_capabilities())

    def orchestrate(
        self,
        *,
        question: str,
        source: dict[str, Any] | None = None,
        content: str | None = None,
        instructions: str | None = None,
        target_schema: dict[str, Any] | None = None,
        endpoint: str | None = None,
        payload: dict[str, Any] | None = None,
        prefer_provider: str | None = None,
        include_markdown: bool = True,
        num_results: int = 5,
    ) -> OrchestrationResult:
        plan = self.planner.build_plan(
            question=question,
            source=source,
            instructions=instructions,
            target_schema=target_schema,
            endpoint=endpoint,
            payload=payload,
            prefer_provider=prefer_provider,
            include_markdown=include_markdown,
            num_results=num_results,
        )

        recommendation = plan.recommendation
        stages = list(plan.steps)

        if recommendation.provider == "api":
            api_result = self.forward_to_api(
                recommendation.communication.get("endpoint") or endpoint or "",
                recommendation.communication.get("payload") or payload or {},
            )
            stages.append(
                {
                    "stage": "api_forward",
                    "status": "completed",
                    "endpoint": recommendation.communication.get("endpoint") or endpoint,
                }
            )
            return OrchestrationResult(
                source=source or {"type": "question"},
                stages=stages,
                result=self._as_dict(api_result),
            )

        if recommendation.provider == "scrapegraph":
            return self._execute_scrapegraph_plan(
                plan=plan,
                content=content,
                prefer_provider=prefer_provider,
            )

        return self._execute_llm_plan(
            plan=plan,
            content=content,
            source=source,
            prefer_provider=prefer_provider,
        )

    def extract_from_url(
        self,
        url: str,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
        prefer_provider: str | None = None,
        include_markdown: bool = True,
    ) -> OrchestrationResult:
        return self.orchestrate(
            question=instructions,
            source={"type": "url", "value": url},
            instructions=instructions,
            target_schema=target_schema,
            prefer_provider=prefer_provider,
            include_markdown=include_markdown,
        )

    def extract_from_text(
        self,
        content: str,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
        prefer_provider: str | None = None,
    ) -> OrchestrationResult:
        return self.orchestrate(
            question=instructions,
            source={"type": "text"},
            content=content,
            instructions=instructions,
            target_schema=target_schema,
            prefer_provider=prefer_provider,
        )

    def enrich_entity(
        self,
        entity_name: str,
        instructions: str | None = None,
        target_schema: dict[str, Any] | None = None,
        prefer_provider: str | None = None,
        num_results: int = 5,
    ) -> OrchestrationResult:
        prompt = instructions or f"Research the entity {entity_name} and return concise structured findings."
        return self.orchestrate(
            question=prompt,
            source={"type": "entity", "value": entity_name},
            instructions=prompt,
            target_schema=target_schema,
            prefer_provider=prefer_provider,
            num_results=num_results,
        )

    def forward_to_api(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.api_client.post(endpoint, payload)

    def _execute_scrapegraph_plan(
        self,
        *,
        plan: ExecutionPlan,
        content: str | None,
        prefer_provider: str | None,
    ) -> OrchestrationResult:
        recommendation = plan.recommendation
        communication = recommendation.communication
        tool_name = communication.get("tool")
        arguments = self._drop_absent_values(self._as_dict(communication.get("arguments")))
        source = plan.context.get("source") or {}
        stages = list(plan.steps)

        if not isinstance(tool_name, str) or not tool_name.strip():
            stages.append(
                {
                    "stage": "scrapegraph_call",
                    "status": "skipped",
                    "reason": "No valid ScrapeGraph tool was selected by the plan.",
                }
            )
            return OrchestrationResult(
                source=source or {"type": "question"},
                stages=stages,
                result={},
            )

        raw_scrape_result = self.scrape_client.call_tool(tool_name, arguments)
        extracted = self._extract_scrape_result(raw_scrape_result)
        if extracted:
            stages.append(
                {
                    "stage": "scrapegraph_call",
                    "status": "completed",
                    "tool": tool_name,
                    "keys": list(extracted.keys()),
                }
            )
        else:
            stages.append(
                {
                    "stage": "scrapegraph_call",
                    "status": "completed",
                    "tool": tool_name,
                }
            )

        markdown = None
        if communication.get("follow_up", {}).get("markdownify") and source.get("type") == "url":
            markdown_payload = self.scrape_client.call_tool(
                "scrapegraph_markdownify",
                {"url": source.get("value")},
            )
            markdown = markdown_payload.get("markdown")
            if markdown:
                stages.append({"stage": "markdownify", "status": "completed"})

        provider_result = self._provider_extract(
            content=content or markdown or self._stringify(extracted),
            instructions=plan.context.get("instructions") or plan.question,
            target_schema=plan.context.get("target_schema") or None,
            prefer_provider=communication.get("follow_up", {}).get("provider_enrichment") or prefer_provider,
        )
        if provider_result:
            stages.append(
                {
                    "stage": "llm_enrichment",
                    "status": "completed",
                    "provider": provider_result["provider"],
                    "keys": list(provider_result["data"].keys()),
                }
            )

        return OrchestrationResult(
            source=source or {"type": "question"},
            stages=stages,
            result=self._merge_sparse_dicts(extracted, provider_result["data"] if provider_result else None),
        )

    def _execute_llm_plan(
        self,
        *,
        plan: ExecutionPlan,
        content: str | None,
        source: dict[str, Any] | None,
        prefer_provider: str | None,
    ) -> OrchestrationResult:
        recommendation = plan.recommendation
        provider_name = recommendation.provider if recommendation.provider != "none" else prefer_provider
        stages = list(plan.steps)

        payload_result: dict[str, Any] | None = None
        if recommendation.action == "extract_structured":
            payload_result = self._provider_extract(
                content=content or "",
                instructions=plan.context.get("instructions") or plan.question,
                target_schema=plan.context.get("target_schema") or None,
                prefer_provider=provider_name,
            )
        else:
            payload_result = self._provider_generate(
                prompt=content or plan.question,
                instructions=plan.context.get("instructions") or plan.question,
                prefer_provider=provider_name,
            )

        result = payload_result["data"] if payload_result and "data" in payload_result else {}
        if payload_result:
            stages.append(
                {
                    "stage": "llm_execution",
                    "status": "completed",
                    "provider": payload_result["provider"],
                    "keys": list(result.keys()) if isinstance(result, dict) else [],
                }
            )

        return OrchestrationResult(
            source=source or {"type": "text"},
            stages=stages,
            result=self._as_dict(result),
        )

    def _provider_extract(
        self,
        content: str,
        instructions: str,
        target_schema: dict[str, Any] | None,
        prefer_provider: str | None,
    ) -> dict[str, Any] | None:
        provider_chain = self._resolve_provider_chain(prefer_provider)
        for provider_name, provider in provider_chain:
            if provider is None or not getattr(provider, "is_configured", True):
                continue

            extract_method = getattr(provider, "extract_structured", None)
            normalize_method = getattr(provider, "normalize_payload", None)

            payload: dict[str, Any] | None = None
            if callable(extract_method):
                payload = self._as_dict(
                    extract_method(
                        content=content,
                        instructions=instructions,
                        target_schema=target_schema,
                    )
                )
            elif callable(normalize_method):
                payload = self._as_dict(
                    normalize_method(
                        payload=content,
                        instructions=instructions,
                        target_schema=target_schema,
                    )
                )

            data = self._extract_structured_data(payload)
            if data:
                return {"provider": provider_name, "data": data, "raw": payload}

        return None

    def _provider_generate(
        self,
        *,
        prompt: str,
        instructions: str,
        prefer_provider: str | None,
    ) -> dict[str, Any] | None:
        provider_chain = self._resolve_provider_chain(prefer_provider)
        for provider_name, provider in provider_chain:
            if provider is None or not getattr(provider, "is_configured", True):
                continue
            generate_method = getattr(provider, "generate_text", None)
            if not callable(generate_method):
                continue
            payload = self._as_dict(
                generate_method(
                    prompt=prompt,
                    system_instruction=instructions,
                )
            )
            text = payload.get("text")
            if isinstance(text, str) and text.strip():
                return {
                    "provider": provider_name,
                    "data": {"text": text.strip()},
                    "raw": payload,
                }
        return None

    def _resolve_provider_chain(self, prefer_provider: str | None) -> list[tuple[str, LLMServiceProtocol | None]]:
        providers = {
            "openai": self.openai_service,
            "anthropic": self.anthropic_service,
        }
        if prefer_provider in providers:
            ordered = [(prefer_provider, providers[prefer_provider])]
            ordered.extend((name, svc) for name, svc in providers.items() if name != prefer_provider)
            return ordered
        return list(providers.items())

    @staticmethod
    def _extract_scrape_result(payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("result"), dict):
            return OrchestrationService._drop_absent_values(payload["result"])
        if isinstance(payload.get("markdown"), str) and payload.get("markdown", "").strip():
            return {"markdown": payload["markdown"].strip()}
        return {}

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
    def _extract_structured_data(payload: dict[str, Any] | None) -> dict[str, Any]:
        if not payload:
            return {}
        parsed = payload.get("parsed")
        if isinstance(parsed, dict):
            return OrchestrationService._drop_absent_values(parsed)
        return {}

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
                compact_list = [entry for entry in item if entry not in (None, "", [], {})]
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
            return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        return str(value)
