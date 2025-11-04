from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DownloadLog(Base):
    __tablename__ = "download_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    distribution_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("distribution.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_version_id: Mapped[str] = mapped_column(
        String(160),
        ForeignKey("resource_version.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_sub: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
