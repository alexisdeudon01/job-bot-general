from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SharedBaseModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="ignore",
    )


class TimestampedSchema(SharedBaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MetadataSchema(SharedBaseModel):
    metadata: dict[str, Any] | None = None