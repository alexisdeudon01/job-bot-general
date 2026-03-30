from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, MetadataMixin, TimestampMixin


class GitHubWorkflowRun(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "github_workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    run_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    conclusion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    html_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    jobs: Mapped[list["GitHubWorkflowJob"]] = relationship(back_populates="workflow_run")


class GitHubWorkflowJob(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "github_workflow_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(ForeignKey("github_workflow_runs.id"), nullable=False, index=True)
    github_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    conclusion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    runner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    log_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow_run: Mapped["GitHubWorkflowRun"] = relationship(back_populates="jobs")


from app.models.pipeline import Provider