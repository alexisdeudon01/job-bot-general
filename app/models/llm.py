from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, MetadataMixin, TimestampMixin


class LLMModel(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "llm_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    model_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    provider: Mapped["Provider | None"] = relationship()
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="llm_model")


class ChatSession(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    llm_model_id: Mapped[int | None] = mapped_column(ForeignKey("llm_models.id"), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open", server_default="open")

    llm_model: Mapped["LLMModel | None"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="chat_session")


class ChatMessage(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    chat_session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Secret(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    secret_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value_masked: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_backend: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


from app.models.pipeline import Provider