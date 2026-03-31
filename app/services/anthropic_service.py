from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from anthropic import Anthropic


class AnthropicService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._model = model or os.getenv("ANTHROPIC_MODEL") or "claude-3-5-haiku-latest"
        self._base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self._timeout = timeout if timeout is not None else self._read_float_env("ANTHROPIC_TIMEOUT", default=60.0)
        self._temperature = temperature if temperature is not None else self._read_float_env("ANTHROPIC_TEMPERATURE", default=0.0)
        self._max_tokens = max_tokens if max_tokens is not None else self._read_int_env("ANTHROPIC_MAX_TOKENS", default=4096)

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def default_model(self) -> str:
        return self._model

    def get_capability_descriptors(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": "anthropic",
                "operation": "generate_text",
                "available": self.is_configured,
                "model": self._model,
                "strengths": [
                    "clear instruction following",
                    "drafting and explanation",
                    "planning-oriented text responses for routing",
                ],
                "best_for": [
                    "provider-side planning notes",
                    "plain-language synthesis",
                    "reasoned text generation without external tools",
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
                    "This service exposes provider capabilities only, not remote MCP tool discovery.",
                    "Use when the task needs language reasoning or drafting in the Anthropic path.",
                ],
            },
            {
                "provider": "anthropic",
                "operation": "extract_structured",
                "available": self.is_configured,
                "model": self._model,
                "strengths": [
                    "generic JSON extraction",
                    "schema-aware transformation",
                    "concise omission of unsupported fields",
                ],
                "best_for": [
                    "extracting structure from text blobs",
                    "transforming text into caller-guided JSON",
                    "normalizing semi-structured content",
                ],
                "inputs": {
                    "required": ["content", "instructions"],
                    "optional": ["target_schema", "context", "model", "temperature", "max_output_tokens", "metadata"],
                },
                "outputs": {
                    "text": "Raw JSON-like text returned by the model",
                    "parsed": "Parsed JSON object when valid JSON is produced",
                },
                "notes": [
                    "The prompt asks for valid JSON only.",
                    "If no schema is supplied, concise JSON is inferred from instructions.",
                ],
            },
            {
                "provider": "anthropic",
                "operation": "normalize_payload",
                "available": self.is_configured,
                "model": self._model,
                "strengths": [
                    "payload cleanup after scraping or API calls",
                    "JSON normalization for arbitrary Python payloads",
                    "light transformation with sparse output preservation",
                ],
                "best_for": [
                    "reshaping mixed payloads",
                    "post-processing upstream tool results",
                ],
                "inputs": {
                    "required": ["payload", "instructions"],
                    "optional": ["target_schema", "context", "model", "temperature", "max_output_tokens", "metadata"],
                },
                "outputs": {
                    "parsed": "Normalized JSON object when parsing succeeds",
                },
                "notes": [
                    "This wraps extract_structured after serializing the payload.",
                ],
            },
        ]

    def describe_capabilities(self) -> dict[str, Any]:
        return {
            "provider": "anthropic",
            "configured": self.is_configured,
            "default_model": self._model,
            "base_url_configured": bool(self._base_url),
            "capabilities": self.get_capability_descriptors(),
        }

    def build_routing_prompt_plan(
        self,
        *,
        question: str,
        preferred_operation: str | None = None,
        context: Mapping[str, Any] | None = None,
        candidate_tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        operation = preferred_operation or self._select_default_operation(question=question, context=context)
        system_instruction = (
            "You are selecting how Anthropic should be used inside this architecture. "
            "Do not invent unavailable external tools. Recommend only one Anthropic operation from this service."
        )
        prompt_sections = [
            "Voici ma question :",
            question.strip(),
            "",
            "Quel outil proposer, comment communiquer avec lui ?",
            "Respond briefly with:",
            "1. selected_operation",
            "2. why_this_operation",
            "3. prompt_strategy",
            "4. sparse_output_guidance",
        ]

        if context:
            prompt_sections.extend(
                [
                    "",
                    "Context:",
                    json.dumps(dict(context), ensure_ascii=False, indent=2, sort_keys=True),
                ]
            )

        if candidate_tools:
            prompt_sections.extend(
                [
                    "",
                    "Candidate provider capabilities:",
                    json.dumps([dict(item) for item in candidate_tools], ensure_ascii=False, indent=2, sort_keys=True, default=str),
                ]
            )

        return {
            "provider": "anthropic",
            "selected_operation": operation,
            "system_instruction": system_instruction,
            "prompt": "\n".join(prompt_sections),
            "execution_hints": {
                "should_expect_json": operation in {"extract_structured", "normalize_payload"},
                "preferred_temperature": 0.0 if operation in {"extract_structured", "normalize_payload"} else self._temperature,
                "preserve_sparse_output": True,
            },
        }

    def generate_text(
        self,
        *,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._create_message(
            prompt=prompt,
            system_instruction=system_instruction,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata,
        )
        return self._normalize_response_payload(response)

    def extract_structured(
        self,
        *,
        content: str,
        instructions: str,
        target_schema: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        prompt = self._build_structured_prompt(
            content=content,
            instructions=instructions,
            target_schema=target_schema,
            context=context,
        )
        response = self._create_message(
            prompt=prompt,
            system_instruction="Return only valid JSON. Do not include markdown fences or explanatory text.",
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata,
        )
        return self._normalize_response_payload(response, expect_json=True)

    def normalize_payload(
        self,
        *,
        payload: Any,
        instructions: str,
        target_schema: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        content = self._serialize_payload(payload)
        return self.extract_structured(
            content=content,
            instructions=instructions,
            target_schema=target_schema,
            context=context,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata,
        )

    def _create_message(
        self,
        *,
        prompt: str,
        system_instruction: str | None,
        model: str | None,
        temperature: float | None,
        max_output_tokens: int | None,
        metadata: Mapping[str, Any] | None,
    ) -> Any:
        client = self.build_client()
        request_kwargs: dict[str, Any] = {
            "model": model or self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens or self._max_tokens,
        }

        if system_instruction:
            request_kwargs["system"] = system_instruction
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        elif self._temperature is not None:
            request_kwargs["temperature"] = self._temperature
        if metadata:
            request_kwargs["metadata"] = dict(metadata)

        return client.messages.create(**request_kwargs)

    def _normalize_response_payload(self, response: Any, *, expect_json: bool = False) -> dict[str, Any]:
        text = self._extract_text(response)
        parsed = None

        if expect_json and text:
            parsed = self._try_parse_json(text)

        return {
            "provider": "anthropic",
            "model": getattr(response, "model", None) or self._model,
            "text": text,
            "parsed": parsed,
            "raw_response_id": getattr(response, "id", None),
            "finish_reason": getattr(response, "stop_reason", None),
            "usage": self._extract_usage(response),
        }

    def _build_structured_prompt(
        self,
        *,
        content: str,
        instructions: str,
        target_schema: Mapping[str, Any] | None,
        context: Mapping[str, Any] | None,
    ) -> str:
        sections = [
            "Perform generic structured extraction and normalization.",
            "If a field is not supported by the source content, prefer omitting it instead of inventing it.",
            f"Instructions:\n{instructions.strip()}",
        ]

        if context:
            sections.append(f"Additional context:\n{json.dumps(dict(context), ensure_ascii=False, indent=2, sort_keys=True)}")

        if target_schema:
            sections.append(
                "Target schema or shape guidance:\n"
                f"{json.dumps(dict(target_schema), ensure_ascii=False, indent=2, sort_keys=True)}"
            )
        else:
            sections.append("No target schema was supplied. Produce concise JSON that best fits the instructions.")

        sections.append(f"Content to analyze:\n{content.strip()}")
        return "\n\n".join(sections)

    def _select_default_operation(self, *, question: str, context: Mapping[str, Any] | None) -> str:
        lowered = question.lower()
        structured_markers = [
            "json",
            "extract",
            "structured",
            "normalize",
            "schema",
            "fields",
        ]

        if any(marker in lowered for marker in structured_markers):
            return "extract_structured"

        if context and any(key in context for key in ["payload", "raw_payload", "response_payload"]):
            return "normalize_payload"

        return "generate_text"

    def _serialize_payload(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    def _extract_text(self, response: Any) -> str | None:
        content = getattr(response, "content", None)
        if not content:
            return None

        parts: list[str] = []
        for block in content:
            text_value = getattr(block, "text", None)
            if text_value:
                parts.append(text_value)
        return "\n".join(parts).strip() or None

    def _extract_usage(self, response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if not usage:
            return {}

        result: dict[str, Any] = {}
        for field_name in ["input_tokens", "output_tokens"]:
            value = getattr(usage, field_name, None)
            if value is not None:
                result[field_name] = value
        if "input_tokens" in result and "output_tokens" in result:
            result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
        return result

    def _try_parse_json(self, value: str) -> Any:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _read_float_env(self, name: str, *, default: float) -> float:
        raw_value = os.getenv(name)
        if raw_value is None or not raw_value.strip():
            return default
        try:
            return float(raw_value)
        except ValueError:
            return default

    def _read_int_env(self, name: str, *, default: int) -> int:
        raw_value = os.getenv(name)
        if raw_value is None or not raw_value.strip():
            return default
        try:
            return int(raw_value)
        except ValueError:
            return default


anthropic_service = AnthropicService()