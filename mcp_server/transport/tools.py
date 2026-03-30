from __future__ import annotations

from mcp_server.clients.orchestrator_client import OrchestratorClient
from mcp_server.services.normalization import (
    build_generate_payload,
    build_run_payload,
    normalize_analyze_result,
    validate_job_url,
)
from mcp_server.utils.errors import MCPServerError


def error_to_dict(error: Exception) -> dict:
    return {"error": str(error)}


def register_tools(mcp, client: OrchestratorClient) -> None:
    @mcp.tool()
    def analyze_job(url: str) -> dict:
        """Analyze a job offer URL and return structured information."""
        try:
            valid_url = validate_job_url(url)
            response = client.post("/api/analyze", {"url": valid_url})
            return normalize_analyze_result(response)
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def generate_documents(job_data: dict, resume_text: str | None = None) -> dict:
        """Generate cover letter and adapted resume for provided job data."""
        try:
            payload = build_generate_payload(job_data, resume_text)
            return client.post("/api/generate", payload)
        except MCPServerError as exc:
            return error_to_dict(exc)

    @mcp.tool()
    def run_full_pipeline(url: str, resume_text: str | None = None) -> dict:
        """Run full analyze + generate pipeline through orchestrator."""
        try:
            payload = build_run_payload(url, resume_text)
            return client.post("/api/run", payload)
        except MCPServerError as exc:
            return error_to_dict(exc)