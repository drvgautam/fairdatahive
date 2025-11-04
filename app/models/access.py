from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccessRequest(Base):
    __tablename__ = "access_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_version_id: Mapped[str] = mapped_column(
        String(160),
        ForeignKey("resource_version.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_sub: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_sub: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
