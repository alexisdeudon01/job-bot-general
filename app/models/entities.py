from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import ActiveMixin, Base, DescriptionMixin, MetadataMixin, NamedMixin, TimestampMixin


class Organization(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    units: Mapped[list["OrganizationalUnit"]] = relationship(back_populates="organization")
    business_entities: Mapped[list["BusinessEntity"]] = relationship(back_populates="organization")
    job_posts: Mapped[list["JobPost"]] = relationship(back_populates="organization")


class OrganizationalUnit(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "organizational_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    parent_unit_id: Mapped[int | None] = mapped_column(ForeignKey("organizational_units.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="units")
    parent_unit: Mapped["OrganizationalUnit | None"] = relationship(remote_side="OrganizationalUnit.id")
    locations: Mapped[list["Location"]] = relationship(back_populates="organizational_unit")
    business_entities: Mapped[list["BusinessEntity"]] = relationship(back_populates="organizational_unit")


class Location(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    organizational_unit_id: Mapped[int | None] = mapped_column(ForeignKey("organizational_units.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    latitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(32), nullable=True)

    organizational_unit: Mapped["OrganizationalUnit | None"] = relationship(back_populates="locations")
    business_entities: Mapped[list["BusinessEntity"]] = relationship(back_populates="location")
    job_posts: Mapped[list["JobPost"]] = relationship(back_populates="location")


class BusinessEntity(Base, TimestampMixin, MetadataMixin, DescriptionMixin, ActiveMixin):
    __tablename__ = "business_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    organizational_unit_id: Mapped[int | None] = mapped_column(ForeignKey("organizational_units.id"), nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    organization: Mapped["Organization | None"] = relationship(back_populates="business_entities")
    organizational_unit: Mapped["OrganizationalUnit | None"] = relationship(back_populates="business_entities")
    location: Mapped["Location | None"] = relationship(back_populates="business_entities")
    outgoing_relationships: Mapped[list["EntityRelationship"]] = relationship(
        foreign_keys="EntityRelationship.source_entity_id",
        back_populates="source_entity",
    )
    incoming_relationships: Mapped[list["EntityRelationship"]] = relationship(
        foreign_keys="EntityRelationship.target_entity_id",
        back_populates="target_entity",
    )


class EntityRelationship(Base, TimestampMixin, MetadataMixin):
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_entity_id: Mapped[int] = mapped_column(ForeignKey("business_entities.id"), nullable=False, index=True)
    target_entity_id: Mapped[int] = mapped_column(ForeignKey("business_entities.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    direction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_entity: Mapped["BusinessEntity"] = relationship(
        foreign_keys=[source_entity_id],
        back_populates="outgoing_relationships",
    )
    target_entity: Mapped["BusinessEntity"] = relationship(
        foreign_keys=[target_entity_id],
        back_populates="incoming_relationships",
    )


class Framework(Base, TimestampMixin, MetadataMixin, NamedMixin, DescriptionMixin, ActiveMixin):
    __tablename__ = "frameworks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Authority(Base, TimestampMixin, MetadataMixin, NamedMixin, DescriptionMixin, ActiveMixin):
    __tablename__ = "authorities"

    id: Mapped[int] = mapped_column(primary_key=True)
    authority_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


from app.models.documents import Application, CV, CVVersion, JobPost