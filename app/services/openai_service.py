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
        self._timeout = timeout if timeout is not None else self._read_float_env("OPENAI_TIMEOUT", default=60.0)
        self._temperature = temperature if temperature is not None else self._read_float_env("OPENAI_TEMPERATURE", default=0.0)

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def default_model(self) -> str:
        return self._model

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
                    "optional": ["system_instruction", "model", "temperature", "max_output_tokens", "metadata"],
                },
                "outputs": {
                    "text": "Generated plain text response",
                    "usage": "Provider token usage when available",
                },
                "notes": [
                    "This service does not expose external MCP tools directly.",
                    "Use this capability when the task is mainly language generation rather than website extraction.",
                ],
            },
            {
                "provider": "openai",
                "operation": "extract_structured",
                "available": self.is_configured,
                "model": self._model,
                "strengths": [
                    "schema-guided extraction",
                    "JSON-oriented normalization",
                    "adapting to caller-provided target schemas",
                ],
                "best_for": [
                    "extracting structured fields from free text",
                    "normalizing messy content into concise JSON",
                    "transforming prior tool output into a desired shape",
                ],
                "inputs": {
                    "required": ["content", "instructions"],
                    "optional": ["target_schema", "context", "model", "temperature", "max_output_tokens", "metadata"],
                },
                "outputs": {
                    "text": "Raw text response expected to contain JSON",
                    "parsed": "Parsed JSON object when valid JSON is returned",
                },
                "notes": [
                    "If no schema is supplied, the service infers a concise JSON structure from instructions.",
                    "Unsupported fields should be omitted instead of invented.",
                ],
            },
            {
                "provider": "openai",
                "operation": "normalize_payload",
                "available": self.is_configured,
                "model": self._model,
                "strengths": [
                    "post-processing arbitrary payloads",
                    "converting dict/list payloads into normalized JSON",
                    "cleaning outputs from other services",
                ],
                "best_for": [
                    "normalizing API or scraper output",
                    "reshaping mixed payloads after enrichment",
                ],
                "inputs": {
                    "required": ["payload", "instructions"],
                    "optional": ["target_schema", "context", "model", "temperature", "max_output_tokens", "metadata"],
                },
                "outputs": {
                    "parsed": "Normalized JSON object when extraction succeeds",
                },
                "notes": [
                    "This is a convenience wrapper over extract_structured after payload serialization.",
                ],
            },
        ]

    def describe_capabilities(self) -> dict[str, Any]:
        return {
            "provider": "openai",
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
            "You are preparing an execution plan for the OpenAI provider inside this architecture. "
            "Do not invent unavailable external tools. Recommend only one OpenAI operation from this service."
        )
        prompt_sections = [
            "Voici ma question :",
            question.strip(),
            "",
            "Quel outil proposer, comment communiquer avec lui ?",
            "Answer briefly with:",
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
            "provider": "openai",
            "selected_operation": operation,
            "system_instruction": system_instruction,
            "prompt": "\n".join(prompt_sections),
            "execution_hints": {
                "should_use_json_mode": operation in {"extract_structured", "normalize_payload"},
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
        response = self._create_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata,
            response_format=None,
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
        response = self._create_response(
            prompt=prompt,
            system_instruction="Return only valid JSON matching the requested structure as closely as possible.",
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata,
            response_format={"type": "json_object"},
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

    def _create_response(
        self,
        *,
        prompt: str,
        system_instruction: str | None,
        model: str | None,
        temperature: float | None,
        max_output_tokens: int | None,
        metadata: Mapping[str, Any] | None,
        response_format: Mapping[str, Any] | None,
    ) -> Any:
        client = self.build_client()
        request_kwargs: dict[str, Any] = {
            "model": model or self._model,
            "input": prompt,
        }

        if system_instruction:
            request_kwargs["instructions"] = system_instruction
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        elif self._temperature is not None:
            request_kwargs["temperature"] = self._temperature
        if max_output_tokens is not None:
            request_kwargs["max_output_tokens"] = max_output_tokens
        if metadata:
            request_kwargs["metadata"] = dict(metadata)
        if response_format:
            request_kwargs["text"] = {"format": dict(response_format)}

        return client.responses.create(**request_kwargs)

    def _normalize_response_payload(self, response: Any, *, expect_json: bool = False) -> dict[str, Any]:
        text = getattr(response, "output_text", None) or self._extract_text_fallback(response)
        parsed = None

        if expect_json and text:
            parsed = self._try_parse_json(text)

        return {
            "provider": "openai",
            "model": getattr(response, "model", None) or self._model,
            "text": text,
            "parsed": parsed,
            "raw_response_id": getattr(response, "id", None),
            "finish_reason": self._extract_finish_reason(response),
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
            "You are performing generic structured extraction and normalization.",
            "Preserve uncertainty by omitting unsupported fields when appropriate.",
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
            sections.append("No target schema was supplied. Infer a concise, useful JSON structure from the instructions.")

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

    def _extract_text_fallback(self, response: Any) -> str | None:
        output = getattr(response, "output", None)
        if not output:
            return None

        parts: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                text_value = getattr(content, "text", None)
                if text_value:
                    parts.append(text_value)
        return "\n".join(parts).strip() or None

    def _extract_finish_reason(self, response: Any) -> str | None:
        output = getattr(response, "output", None)
        if not output:
            return None

        for item in output:
            status = getattr(item, "status", None)
            if status:
                return status
        return None

    def _extract_usage(self, response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if not usage:
            return {}

        if isinstance(usage, dict):
            return usage

        result: dict[str, Any] = {}
        for field_name in ["input_tokens", "output_tokens", "total_tokens"]:
            value = getattr(usage, field_name, None)
            if value is not None:
                result[field_name] = value
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