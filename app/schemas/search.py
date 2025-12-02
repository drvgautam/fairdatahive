from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.resource import ResourceVersionSummary


class FacetEntry(BaseModel):
    value: str
    count: int


class FacetGroup(BaseModel):
    themes: list[FacetEntry] = Field(default_factory=list)
    licenses: list[FacetEntry] = Field(default_factory=list)
    formats: list[FacetEntry] = Field(default_factory=list)


class SearchHit(BaseModel):
    resource: ResourceVersionSummary
    score: float | None = None


class SearchResponse(BaseModel):
    total: int = 0
    page: int = 1
    size: int = 20
    mode_used: Literal["keyword", "semantic", "auto"] = "keyword"
    results: list[SearchHit] = Field(default_factory=list)
    facets: FacetGroup = Field(default_factory=FacetGroup)


class SuggestResponse(BaseModel):
    suggestions: list[str] = Field(default_factory=list)


class CatalogStats(BaseModel):
    total_resources: int
    total_versions: int
    total_published: int
    total_drafts: int
    total_distributions: int
    by_theme: list[FacetEntry] = Field(default_factory=list)
    by_license: list[FacetEntry] = Field(default_factory=list)
