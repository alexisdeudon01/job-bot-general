from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    name: str
    status: str = "unknown"
    detail: str | None = None
    latency_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: int | float | str
    trend: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DashboardOverview(BaseModel):
    generated_at: datetime
    status: str = "ok"
    metrics: list[DashboardMetric] = Field(default_factory=list)
    services: list[ServiceStatus] = Field(default_factory=list)
    recent_pipeline_runs: list[dict[str, Any]] = Field(default_factory=list)
    recent_github_runs: list[dict[str, Any]] = Field(default_factory=list)