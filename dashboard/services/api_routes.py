from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DashboardApiRoutes:
    health: str = "/health"
    overview: str = "/api/v1/dashboard/overview"
    entities: str = "/api/v1/dashboard/entities"
    llm_history: str = "/api/v1/dashboard/llm-history"
    mcp_status: str = "/api/v1/dashboard/mcp-status"
    db_schema: str = "/api/v1/dashboard/db-schema"
    provider_status: str = "/api/v1/providers/status"
    pipeline_runs: str = "/api/v1/pipeline/runs"
    github_actions_runs: str = "/api/v1/github-actions/runs"


ROUTES = DashboardApiRoutes()