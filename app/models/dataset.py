from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.resource import ResourceVersion


class Dataset(Base):
    __tablename__ = "dataset"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    resource_version_id: Mapped[str] = mapped_column(
        String(160),
        ForeignKey("resource_version.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    resource_version: Mapped["ResourceVersion"] = relationship(
        "ResourceVersion", back_populates="datasets"
    )
    distributions: Mapped[list["Distribution"]] = relationship(
        "Distribution",
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Distribution(Base):
    __tablename__ = "distribution"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("dataset.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    dist_type: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    access_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(80), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    issued: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="distributions")
    data_service: Mapped["DataService | None"] = relationship(
        "DataService",
        back_populates="distribution",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )


class DataService(Base):
    __tablename__ = "data_service"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    distribution_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("distribution.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    distribution: Mapped[Distribution] = relationship(
        "Distribution", back_populates="data_service"
    )
