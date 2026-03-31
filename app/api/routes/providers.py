from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.openai_agents_service import openai_agents_service
from app.services.openai_service import openai_service

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("/health")
def provider_health() -> dict[str, Any]:
    """Return health status for all configured LLM and MCP providers."""
    return {
        "status": "ok",
        "providers": {
            "openai": {
                "configured": openai_service.is_configured,
                "model": openai_service.default_model,
            },
            "openai_agents": {
                "configured": openai_agents_service.is_configured,
                "model": openai_agents_service.default_model,
                "mcp_servers": openai_agents_service.describe_mcp_servers(),
            },
        },
    }


@router.get("/capabilities")
def provider_capabilities() -> dict[str, Any]:
    """Return full capability descriptors for all providers."""
    return {
        "openai": openai_service.get_capability_descriptors(),
        "openai_agents": openai_agents_service.get_capability_descriptors(),
        "mcp_transports_supported": ["stdio", "sse", "streamable_http"],
    }


@router.get("/mcp-servers")
def mcp_servers() -> list[dict[str, Any]]:
    """Return metadata for all registered MCP servers."""
    return openai_agents_service.describe_mcp_servers()
