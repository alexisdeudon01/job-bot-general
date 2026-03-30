from __future__ import annotations

from mcp_server.utils.errors import PayloadNormalizationError


def normalize_analyze_result(response: dict) -> dict:
    """
    Normalise la réponse analyze pour conserver la forme plate
    attendue par les clients MCP historiques.
    """
    if not isinstance(response, dict):
        raise PayloadNormalizationError("Unexpected analyze response format")

    if "data" in response and isinstance(response["data"], dict):
        return response["data"]

    return response


def build_generate_payload(job_data: dict, resume_text: str | None = None) -> dict:
    if not isinstance(job_data, dict):
        raise PayloadNormalizationError("job_data must be an object")

    payload = {"job_data": job_data}
    if resume_text:
        payload["resume_text"] = resume_text
    return payload


def build_run_payload(url: str, resume_text: str | None = None) -> dict:
    if not url or not isinstance(url, str):
        raise PayloadNormalizationError("A valid job URL is required")

    payload = {"url": url}
    if resume_text:
        payload["resume_text"] = resume_text
    return payload


def validate_job_url(url: str) -> str:
    if not url or not isinstance(url, str):
        raise PayloadNormalizationError("A valid job URL is required")
    return url