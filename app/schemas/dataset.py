from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DataServiceCreate(BaseModel):
    endpoint_url: str
    description: str | None = None


class DataServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    endpoint_url: str
    description: str | None = None


class DistributionCreate(BaseModel):
    dist_type: Literal["upload", "external", "api"] = "upload"
    title: str | None = None
    description: str | None = None
    upload_token: str | None = Field(
        default=None,
        description="Object key returned by /files/upload (for type=upload).",
    )
    access_url: str | None = Field(
        default=None,
        description="Externally hosted access URL (for type=external/api).",
    )
    media_type: str | None = None
    checksum_sha256: str | None = None
    byte_size: int | None = None
    data_service: DataServiceCreate | None = None


class DistributionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dist_type: str
    title: str | None = None
    description: str | None = None
    access_url: str | None = None
    download_url: str | None = None
    media_type: str | None = None
    checksum_sha256: str | None = None
    byte_size: int | None = None
    issued: datetime
    data_service: DataServiceRead | None = None


class DatasetCreate(BaseModel):
    distributions: list[DistributionCreate] = Field(default_factory=list)


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    distributions: list[DistributionRead] = Field(default_factory=list)


class UploadResponse(BaseModel):
    upload_token: str = Field(description="MinIO object key (use as upload_token).")
    object_key: str
    checksum_sha256: str
    byte_size: int
    media_type: str | None = None
    original_filename: str
    extracted_files: list["UploadResponse"] = Field(default_factory=list)


UploadResponse.model_rebuild()


class PresignedDownloadResponse(BaseModel):
    download_url: str
    expires_in: int
    object_key: str
