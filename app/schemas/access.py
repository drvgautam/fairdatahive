from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccessRequestCreate(BaseModel):
    resource_version_id: str
    message: str | None = Field(default=None, max_length=1024)


class AccessRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_version_id: str
    requester_sub: str
    owner_sub: str
    status: Literal["pending", "accepted", "rejected", "revoked"]
    message: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    expires_at: datetime


class AccessStatus(BaseModel):
    resource_version_id: str
    is_private: bool
    has_access: bool
    is_owner: bool
    pending_request_id: int | None = None
