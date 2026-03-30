from fastapi import APIRouter

from app.integrations.github_actions import list_github_action_runs
from app.integrations.providers import get_provider_statuses
from app.schemas.dashboard import DashboardOverview, ServiceStatus
from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/overview", response_model=DashboardOverview)
def get_dashboard_overview() -> DashboardOverview:
    return dashboard_service.get_overview()


@router.get("/providers/status", response_model=list[ServiceStatus])
def get_providers_status() -> list[ServiceStatus]:
    return get_provider_statuses()


@router.get("/github-actions/runs")
def get_github_actions_runs() -> list[dict]:
    return list_github_action_runs()