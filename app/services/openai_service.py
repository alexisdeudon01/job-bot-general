from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from openai import OpenAI


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
        self._timeout = (
            timeout
            if timeout is not None
            else self._read_float_env("OPENAI_TIMEOUT", default=60.0)
        )
        self._temperature = (
            temperature
            if temperature is not None
            else self._read_float_env("OPENAI_TEMPERATURE", default=0.0)
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def default_model(self) -> str:
        return self._model

    def build_client(self) -> OpenAI:
        """Build and return an OpenAI client instance."""
        kwargs: dict[str, Any] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._timeout:
            kwargs["timeout"] = self._timeout
        return OpenAI(**kwargs)

    def get_capability_descriptors(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": "openai",
                "operation": "generate_text",
                "available": self.is_configured,
                "model": self._model,
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
                    "optional": [
                        "system_instruction",
                        "model",
                        "temperature",
                        "max_output_tokens",
                        "metadata",
                    ],
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
                "available": self.is_configured,
                "model": self._model,
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

    def describe_capabilities(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "configured": self.is_configured,
            "model": self._model,
            "capabilities": self.get_capability_descriptors(),
        }

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
        return {
            "provider": "openai",
            "selected_operation": operation,
            "question": question,
            "candidate_tools": candidate_tools or [],
        }

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
        client = self.build_client()
        effective_model = model or self._model
        effective_temperature = (
            temperature if temperature is not None else self._temperature
        )

        messages: list[dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "temperature": effective_temperature,
        }
        if max_output_tokens:
            kwargs["max_tokens"] = max_output_tokens

        response = client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        usage = self._extract_usage(response)

        return {
            "provider": "openai",
            "model": effective_model,
            "text": text,
            "usage": usage,
        }

    def extract_structured(
        self,
        *,
        content: str,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        schema_hint = ""
        if target_schema:
            schema_hint = (
                f"\n\nTarget JSON schema:\n{json.dumps(target_schema, indent=2)}"
            )

        prompt = f"{instructions}{schema_hint}\n\nContent:\n{content}"
        client = self.build_client()

        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a structured data extraction assistant. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        parsed = self._try_parse_json(text)
        usage = self._extract_usage(response)

        return {
            "provider": "openai",
            "model": self._model,
            "parsed": parsed,
            "text": text,
            "usage": usage,
        }

    def normalize_payload(
        self,
        *,
        payload: Any,
        instructions: str,
        target_schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        serialized = self._serialize_payload(payload)
        return self.extract_structured(
            content=serialized,
            instructions=instructions,
            target_schema=target_schema,
        )

    def _infer_operation(self, lowered: str, context: dict[str, Any] | None) -> str:
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
        if context and any(
            key in context for key in ["payload", "raw_payload", "response_payload"]
        ):
            return "normalize_payload"
        return "generate_text"

    def _serialize_payload(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        return json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True, default=str
        )

    def _extract_usage(self, response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if not usage:
            return {}
        result: dict[str, Any] = {}
        for field_name in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            value = getattr(usage, field_name, None)
            if value is not None:
                result[field_name] = value
        # Normalize to input_tokens / output_tokens for consistency
        if "prompt_tokens" in result:
            result["input_tokens"] = result.pop("prompt_tokens")
        if "completion_tokens" in result:
            result["output_tokens"] = result.pop("completion_tokens")
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


openai_service = OpenAIService()
