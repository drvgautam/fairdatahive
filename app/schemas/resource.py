from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.schemas.dataset import DatasetCreate, DatasetRead


class ResourceCreate(BaseModel):
    scope: str = Field(default="public", description="'public' or a project_id.")
    title: str = Field(min_length=1, max_length=512)
    description: str = Field(
        min_length=50, description="Must be at least 50 characters."
    )
    keywords: list[str] = Field(
        default_factory=list, description="At least 2 keywords required."
    )
    theme: str = Field(min_length=1)

    license_id: str | None = None
    doi: str | None = None
    language: str | None = None

    provenance: str | None = None
    rights_statement: str | None = None
    spatial: str | None = None
    temporal: str | None = None
    assumptions: str | None = None
    technique: str | None = None
    post_processing: str | None = None

    is_private: bool = False
    access_rights: list[str] = Field(default_factory=list)

    datasets: list[DatasetCreate] = Field(default_factory=list)

    @field_validator("keywords")
    @classmethod
    def _min_keywords(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise PydanticCustomError(
                "keywords.min_items",
                "At least 2 keywords required.",
            )
        return v


class ResourceVersionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, min_length=50)
    keywords: list[str] | None = None
    theme: str | None = None
    license_id: str | None = None
    doi: str | None = None
    language: str | None = None
    provenance: str | None = None
    rights_statement: str | None = None
    spatial: str | None = None
    temporal: str | None = None
    assumptions: str | None = None
    technique: str | None = None
    post_processing: str | None = None
    is_private: bool | None = None
    access_rights: list[str] | None = None


class ResourceVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    base_resource_id: str
    previous_version_id: str | None = None
    title: str
    description: str
    state: Literal["draft", "published", "deprecated"]
    publisher_sub: str
    issued: datetime
    modified: datetime
    theme: str | None = None
    keywords: list[str] | None = None
    license_id: str | None = None
    doi: str | None = None
    language: str | None = None
    provenance: str | None = None
    rights_statement: str | None = None
    spatial: str | None = None
    temporal: str | None = None
    assumptions: str | None = None
    technique: str | None = None
    post_processing: str | None = None
    is_private: bool = False
    access_rights: list[str] | None = None
    data_deleted: bool = False
    dcat_ap_report: str | None = None
    download_count: int = 0
    scope: str | None = None
    can_manage: bool = False
    datasets: list[DatasetRead] = Field(default_factory=list)


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: str
    owner_sub: str
    created_at: datetime
    current_version_id: str | None = None


class ResourceVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    base_resource_id: str
    title: str
    state: str
    issued: datetime
    modified: datetime
    publisher_sub: str
    theme: str | None = None
    license_id: str | None = None
    is_private: bool = False
    data_deleted: bool = False


class NewVersionRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    theme: str | None = None
    license_id: str | None = None
    doi: str | None = None
    language: str | None = None
    provenance: str | None = None
    rights_statement: str | None = None
    spatial: str | None = None
    temporal: str | None = None
    assumptions: str | None = None
    technique: str | None = None
    post_processing: str | None = None
    is_private: bool | None = None
    access_rights: list[str] | None = None
    datasets: list[DatasetCreate] = Field(default_factory=list)
