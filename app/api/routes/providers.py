"""Placeholder provider routes noted during MCP audit.

This file is intentionally minimal because the current task is audit-only.
It exists so the audit summary can reference a concrete candidate path.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("/health")
def provider_health_placeholder() -> dict:
    return {
        "status": "not_implemented",
        "message": "Placeholder route created during audit phase.",
    }