from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._types import StringArray, vector_column_type

if TYPE_CHECKING:
    from app.models.dataset import Dataset


class Resource(Base):
    __tablename__ = "resource"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_sub: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    current_version_id: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )

    versions: Mapped[list["ResourceVersion"]] = relationship(
        "ResourceVersion",
        back_populates="resource",
        foreign_keys="ResourceVersion.base_resource_id",
        order_by="ResourceVersion.issued",
        cascade="all, delete-orphan",
    )


class ResourceVersion(Base):
    __tablename__ = "resource_version"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    base_resource_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("resource.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_version_id: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    publisher_sub: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    issued: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    theme: Mapped[str | None] = mapped_column(String(128), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(StringArray, nullable=True)

    license_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)

    provenance: Mapped[str | None] = mapped_column(Text, nullable=True)
    rights_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    spatial: Mapped[str | None] = mapped_column(String(256), nullable=True)
    temporal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    technique: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_processing: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    access_rights: Mapped[list[str] | None] = mapped_column(StringArray, nullable=True)

    embedding = mapped_column(vector_column_type(768), nullable=True)

    data_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dcat_ap_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    resource: Mapped[Resource] = relationship(
        "Resource",
        back_populates="versions",
        foreign_keys=[base_resource_id],
    )

    datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset",
        back_populates="resource_version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
