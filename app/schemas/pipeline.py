from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PipelineRequest(BaseModel):
    source: str = "manual"
    payload: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class PipelineStepResult(BaseModel):
    step: str
    status: str = "queued"
    detail: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)


class PipelineRunResponse(BaseModel):
    run_id: str
    pipeline_type: str
    status: str
    created_at: datetime
    steps: list[PipelineStepResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineRunSummary(BaseModel):
    run_id: str
    pipeline_type: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    source: str = "manual"


class PipelineRunsResponse(BaseModel):
    runs: list[PipelineRunSummary] = Field(default_factory=list)