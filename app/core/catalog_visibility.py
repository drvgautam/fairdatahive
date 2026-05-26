"""Predicates for resources visible on anonymous catalog/search/harvest APIs."""

from __future__ import annotations

from sqlalchemy.sql import ColumnElement

from app.models.resource import ResourceVersion


def public_catalog_version_filters() -> tuple[ColumnElement[bool], ...]:
    """Published, non-private versions eligible for public discovery."""
    return (
        ResourceVersion.state == "published",
        ResourceVersion.is_private.is_(False),
        ResourceVersion.data_deleted.is_(False),
    )


def oai_harvest_version_filters() -> tuple[ColumnElement[bool], ...]:
    """Versions exposed via OAI-PMH (public published or deprecated)."""
    return (
        ResourceVersion.state.in_(("published", "deprecated")),
        ResourceVersion.is_private.is_(False),
    )
