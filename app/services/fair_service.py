from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset, Distribution
from app.models.resource import ResourceVersion
from app.models.user import UserProfile
from app.schemas.fair import FairDimension, FairScore


SUGGESTIONS: dict[str, str] = {
    "has_title": "Add a descriptive title to the resource.",
    "description_adequate": "Expand the description to at least 50 characters.",
    "has_keywords": "Add at least two keywords describing the topic.",
    "has_theme": "Set a theme so the resource appears in the right category.",
    "has_doi": (
        "Register a DOI (e.g. via Zenodo) and add it here for a globally persistent "
        "identifier."
    ),
    "has_distribution": "Attach at least one dataset with a distribution.",
    "access_rights_defined": (
        "For private resources, list the user IDs (sub claims) allowed to download."
    ),
    "access_url_present": (
        "Set an access_url on each external distribution so consumers can reach the "
        "data."
    ),
    "has_license": "Add a license_id (e.g. CC-BY-4.0) to enable reuse.",
    "has_language": "Set the language field using a BCP-47 code (e.g. 'en').",
    "media_types_present": "Set media_type (IANA) on each distribution.",
    "publisher_resolvable": (
        "Create or update your user profile so the publisher resolves to a name."
    ),
    "has_provenance": (
        "Add a provenance description explaining how this data was generated."
    ),
    "has_rights_statement": (
        "Add a rights statement explaining the terms of use in plain language."
    ),
    "checksum_on_uploads": (
        "Make sure all uploaded distributions have a SHA-256 checksum recorded."
    ),
}


async def _distributions(
    db: AsyncSession, version_id: str
) -> list[Distribution]:
    stmt = (
        select(Distribution)
        .join(Dataset, Distribution.dataset_id == Dataset.id)
        .where(Dataset.resource_version_id == version_id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _publisher_resolvable(db: AsyncSession, sub: str) -> bool:
    profile = await db.get(UserProfile, sub)
    return profile is not None and bool(profile.display_name)


def _findable_checks(version: ResourceVersion) -> dict[str, bool]:
    return {
        "has_title": bool(version.title and version.title.strip()),
        "description_adequate": bool(
            version.description and len(version.description) >= 50
        ),
        "has_keywords": bool(version.keywords and len(version.keywords) >= 2),
        "has_theme": bool(version.theme and version.theme.strip()),
        "has_doi": bool(version.doi),
    }


def _accessible_checks(
    version: ResourceVersion, dists: list[Distribution]
) -> dict[str, bool]:
    access_rights_defined = (not version.is_private) or bool(
        version.access_rights
    )
    access_url_present = (
        all((d.access_url or d.download_url) for d in dists) if dists else False
    )
    return {
        "has_distribution": bool(dists),
        "access_rights_defined": access_rights_defined,
        "access_url_present": access_url_present,
    }


def _interoperable_checks(
    version: ResourceVersion,
    dists: list[Distribution],
    publisher_known: bool,
) -> dict[str, bool]:
    return {
        "has_license": bool(version.license_id),
        "has_language": bool(version.language),
        "media_types_present": bool(dists) and all(d.media_type for d in dists),
        "publisher_resolvable": publisher_known,
    }


def _reusable_checks(
    version: ResourceVersion, dists: list[Distribution]
) -> dict[str, bool]:
    upload_dists = [d for d in dists if d.dist_type == "upload"]
    return {
        "has_provenance": bool(version.provenance and len(version.provenance) > 20),
        "has_rights_statement": bool(version.rights_statement),
        "checksum_on_uploads": (
            all(d.checksum_sha256 for d in upload_dists) if upload_dists else True
        ),
    }


def _dimension_score(checks: dict[str, bool]) -> float:
    if not checks:
        return 0.0
    passed = sum(1 for v in checks.values() if v)
    return round(passed / len(checks), 4)


def _suggestions(all_checks: Iterable[tuple[str, bool]]) -> list[str]:
    out: list[str] = []
    for name, ok in all_checks:
        if not ok and name in SUGGESTIONS:
            out.append(SUGGESTIONS[name])
    return out


async def compute_fair_score(
    db: AsyncSession, version: ResourceVersion
) -> FairScore:
    dists = await _distributions(db, version.id)
    publisher_known = await _publisher_resolvable(db, version.publisher_sub)

    findable = _findable_checks(version)
    accessible = _accessible_checks(version, dists)
    interoperable = _interoperable_checks(version, dists, publisher_known)
    reusable = _reusable_checks(version, dists)

    dims = {
        "findable": FairDimension(score=_dimension_score(findable), checks=findable),
        "accessible": FairDimension(
            score=_dimension_score(accessible), checks=accessible
        ),
        "interoperable": FairDimension(
            score=_dimension_score(interoperable), checks=interoperable
        ),
        "reusable": FairDimension(score=_dimension_score(reusable), checks=reusable),
    }
    overall = round(
        sum(d.score for d in dims.values()) / len(dims),
        4,
    )

    all_checks = (
        list(findable.items())
        + list(accessible.items())
        + list(interoperable.items())
        + list(reusable.items())
    )
    return FairScore(score=overall, dimensions=dims, suggestions=_suggestions(all_checks))
