from datetime import datetime
from typing import Any

from pydantic import Field

from shared.schemas.base import SharedBaseModel


class PipelineRunBase(SharedBaseModel):
    run_type: str = Field(..., examples=["analyze"])
    status: str = Field(default="pending", examples=["pending", "running", "success", "error"])
    trigger_source: str | None = Field(default=None, examples=["api", "dashboard"])
    job_url: str | None = None
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


class PipelineRunCreate(PipelineRunBase):
    pass


class PipelineRunRead(PipelineRunBase):
    id: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ServiceRunRead(SharedBaseModel):
    id: int
    pipeline_run_id: int
    service_name: str
    status: str
    provider_name: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


class RunEventRead(SharedBaseModel):
    id: int
    pipeline_run_id: int
    service_run_id: int | None = None
    level: str = "info"
    event_type: str
    message: str
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None