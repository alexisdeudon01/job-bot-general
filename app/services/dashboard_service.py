from datetime import datetime

from app.integrations.github_actions import list_github_action_runs
from app.integrations.providers import get_provider_statuses
from app.schemas.dashboard import DashboardMetric, DashboardOverview
from app.services.pipeline_service import pipeline_service


class DashboardService:
    def get_overview(self) -> DashboardOverview:
        pipeline_runs = pipeline_service.list_runs().runs
        github_runs = list_github_action_runs()
        services = get_provider_statuses()

        metrics = [
            DashboardMetric(
                key="pipeline_runs",
                label="Pipeline runs",
                value=len(pipeline_runs),
                trend="stable",
            ),
            DashboardMetric(
                key="github_runs",
                label="GitHub Actions runs",
                value=len(github_runs),
                trend="up",
            ),
            DashboardMetric(
                key="services_monitored",
                label="Services monitored",
                value=len(services),
                trend="stable",
            ),
        ]

        return DashboardOverview(
            generated_at=datetime.utcnow(),
            status="ok",
            metrics=metrics,
            services=services,
            recent_pipeline_runs=[run.model_dump() for run in pipeline_runs[:5]],
            recent_github_runs=github_runs[:5],
        )


dashboard_service = DashboardService()