from __future__ import annotations

import json
import os
from functools import cached_property
from typing import Any

from openai import OpenAI

_CAPABILITY_DESCRIPTORS: list[dict[str, Any]] = [
    {
        "provider": "openai",
        "operation": "generate_text",
        "strengths": [
            "general reasoning and drafting",
            "instruction following for concise text generation",
            "lightweight planning before tool routing",
        ],
        "best_for": [
            "plain language answers",
            "rewriting or summarizing text",
            "creating a tool-selection recommendation",
        ],
        "inputs": {
            "required": ["prompt"],
            "optional": ["system_instruction", "model", "temperature", "max_output_tokens", "metadata"],
        },
        "outputs": {
            "text": "Generated plain text response",
            "usage": "Provider token usage when available",
        },
        "notes": [
            "Use this capability for direct language generation without external tools.",
            "For MCP tool-enabled agent execution, use OpenAIAgentsService instead.",
        ],
    },
    {
        "provider": "openai",
        "operation": "extract_structured",
        "strengths": [
            "JSON-mode structured extraction",
            "schema-guided field extraction from raw text",
        ],
        "best_for": [
            "extracting structured job data from raw text",
            "normalizing API payloads to a target schema",
        ],
        "inputs": {
            "required": ["content", "instructions"],
            "optional": ["target_schema", "model", "temperature"],
        },
        "outputs": {
            "parsed": "Parsed JSON object when extraction succeeds",
            "text": "Raw text response as fallback",
        },
    },
]

_STRUCTURED_MARKERS = frozenset(["json", "extract", "structured", "normalize", "schema", "fields"])
_PAYLOAD_KEYS = frozenset(["payload", "raw_payload", "response_payload"])


class OpenAIService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        temperature: float | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._timeout = timeout if timeout is not None else _read_float_env("OPENAI_TIMEOUT", default=60.0)
        self._temperature = temperature if temperature is not None else _read_float_env("OPENAI_TEMPERATURE", default=0.0)

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def default_model(self) -> str:
        return self._model

    @cached_property
    def _client(self) -> OpenAI:
        kwargs: dict[str, Any] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._timeout:
            kwargs["timeout"] = self._timeout
        return OpenAI(**kwargs)

    def describe_capabilities(self) -> dict[str, Any]:
        descriptors = [{**d, "available": self.is_configured, "model": self._model} for d in _CAPABILITY_DESCRIPTORS]
        return {"provider": "openai", "configured": self.is_configured, "model": self._model, "capabilities": descriptors}

    def build_routing_prompt_plan(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: dict[str, Any] | None = None,
        candidate_tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        lowered = question.lower()
        operation = preferred_operation or self._infer_operation(lowered, context)
        return {"provider": "openai", "selected_operation": operation, "question": question, "candidate_tools": candidate_tools or []}

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
        effective_model = model or self._model
        effective_temperature = temperature if temperature is not None else self._temperature

        messages: list[dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {"model": effective_model, "messages": messages, "temperature": effective_temperature}
        if max_output_tokens:
            kwargs["max_tokens"] = max_output_tokens

        response = self._client.chat.completions.create(**kwargs)
        return {
            "provider": "openai",
            "model": effective_model,
            "text": response.choices[0].message.content or "",
            "usage": _extract_usage(response),
        }

    def extract_structured(
        self,
        *,
        content: str,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        schema_hint = f"\n\nTarget JSON schema:\n{json.dumps(target_schema, indent=2)}" if target_schema else ""
        prompt = f"{instructions}{schema_hint}\n\nContent:\n{content}"

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are a structured data extraction assistant. Always respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        return {
            "provider": "openai",
            "model": self._model,
            "parsed": _try_parse_json(text),
            "text": text,
            "usage": _extract_usage(response),
        }

    def normalize_payload(
        self,
        *,
        payload: Any,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.extract_structured(
            content=payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            instructions=instructions,
            target_schema=target_schema,
        )

    def _infer_operation(self, lowered: str, context: dict[str, Any] | None) -> str:
        if any(marker in lowered for marker in _STRUCTURED_MARKERS):
            return "extract_structured"
        if context and _PAYLOAD_KEYS & context.keys():
            return "normalize_payload"
        return "generate_text"


def _extract_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if not usage:
        return {}
    mapping = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens", "total_tokens": "total_tokens"}
    return {mapping[k]: v for k in mapping if (v := getattr(usage, k, None)) is not None}


def _try_parse_json(value: str) -> Any:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _read_float_env(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if not raw or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


openai_service = OpenAIService()
