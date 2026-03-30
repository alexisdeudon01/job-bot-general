from fastapi import APIRouter

from app.integrations.github_actions import list_github_action_runs
from app.integrations.providers import get_provider_statuses
from app.schemas.dashboard import DashboardOverview, ServiceStatus
from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/overview", response_model=DashboardOverview)
def get_dashboard_overview() -> DashboardOverview:
    return dashboard_service.get_overview()


@router.get("/dashboard/entities")
def get_dashboard_entities() -> dict:
    return dashboard_service.get_entities_detail()


@router.get("/dashboard/llm-history")
def get_dashboard_llm_history() -> dict:
    return dashboard_service.get_llm_history_summary()


@router.get("/dashboard/mcp-status")
def get_dashboard_mcp_status() -> dict:
    return dashboard_service.get_mcp_status_detail()


@router.get("/dashboard/db-schema")
def get_dashboard_db_schema() -> dict:
    return dashboard_service.get_db_schema_graph()


@router.get("/providers/status", response_model=list[ServiceStatus])
def get_providers_status() -> list[ServiceStatus]:
    return get_provider_statuses()


@router.get("/github-actions/runs")
def get_github_actions_runs() -> list[dict]:
    return list_github_action_runs()