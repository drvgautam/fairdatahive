from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sub: str
    display_name: str | None = None
    email: str | None = None
    created_at: datetime


class UserProfileUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None


class DownloadStats(BaseModel):
    total_downloads: int
    unique_downloaders: int
    downloads_by_version: dict[str, int]
    downloads_by_month: dict[str, int]
