from __future__ import annotations

from pydantic import BaseModel, Field


class FairDimension(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    checks: dict[str, bool]


class FairScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    dimensions: dict[str, FairDimension]
    suggestions: list[str] = Field(default_factory=list)


class LicenseInfo(BaseModel):
    id: str
    label: str
    url: str
    spdx: str


class ThemeInfo(BaseModel):
    id: str
    label: str
