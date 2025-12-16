from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_sub: str
    type: str
    message: str
    resource_version_id: str | None = None
    related_id: str | None = None
    read: bool
    created_at: datetime
