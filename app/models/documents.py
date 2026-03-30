from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, MetadataMixin, TimestampMixin


class CV(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "cvs"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(ForeignKey("cv_versions.id"), nullable=True, index=True)

    versions: Mapped[list["CVVersion"]] = relationship(
        back_populates="cv",
        foreign_keys="CVVersion.cv_id",
    )
    current_version: Mapped["CVVersion | None"] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
    )
    applications: Mapped[list["Application"]] = relationship(back_populates="cv")


class CVVersion(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "cv_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cv_id: Mapped[int] = mapped_column(ForeignKey("cvs.id"), nullable=False, index=True)
    version_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    cv: Mapped["CV"] = relationship(
        back_populates="versions",
        foreign_keys=[cv_id],
    )


class JobPost(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "job_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_policy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="discovered", server_default="discovered")

    organization: Mapped["Organization | None"] = relationship(back_populates="job_posts")
    location: Mapped["Location | None"] = relationship(back_populates="job_posts")
    applications: Mapped[list["Application"]] = relationship(back_populates="job_post")


class Application(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_post_id: Mapped[int] = mapped_column(ForeignKey("job_posts.id"), nullable=False, index=True)
    cv_id: Mapped[int | None] = mapped_column(ForeignKey("cvs.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", server_default="draft")
    source_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cover_letter_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    job_post: Mapped["JobPost"] = relationship(back_populates="applications")
    cv: Mapped["CV | None"] = relationship(back_populates="applications")


from app.models.entities import Location, Organization