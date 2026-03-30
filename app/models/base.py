from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MetadataMixin:
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)


class NamedMixin:
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class DescriptionMixin:
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActiveMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")