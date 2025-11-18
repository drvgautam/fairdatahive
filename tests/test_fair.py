from __future__ import annotations

import pytest

from app.models.resource import ResourceVersion
from app.models.dataset import Dataset, Distribution
from app.services.fair_service import compute_fair_score

pytestmark = pytest.mark.asyncio


async def _make_version(db, **overrides) -> ResourceVersion:
    from app.services.resource_service import (
        make_dataset_id,
        make_distribution_id,
        make_resource_id,
        make_version_id,
    )
    from app.models.resource import Resource

    base_id = overrides.pop("base_id", make_resource_id())
    version_id = overrides.pop("version_id", make_version_id(base_id))

    resource = Resource(
        id=base_id, scope="public", owner_sub="owner-1", current_version_id=None
    )
    db.add(resource)
    version = ResourceVersion(
        id=version_id,
        base_resource_id=base_id,
        title=overrides.get("title", "Test resource"),
        description=overrides.get(
            "description",
            "A reasonably long description that goes beyond fifty characters.",
        ),
        state=overrides.get("state", "draft"),
        publisher_sub="owner-1",
        theme=overrides.get("theme", "Electrochemistry"),
        keywords=overrides.get("keywords", ["a", "b"]),
        license_id=overrides.get("license_id"),
        doi=overrides.get("doi"),
        language=overrides.get("language"),
        provenance=overrides.get("provenance"),
        rights_statement=overrides.get("rights_statement"),
        is_private=overrides.get("is_private", False),
        access_rights=overrides.get("access_rights"),
    )
    db.add(version)
    await db.flush()

    if "with_distribution" in overrides:
        ds = Dataset(id=make_dataset_id(), resource_version_id=version_id)
        db.add(ds)
        await db.flush()
        dist = Distribution(
            id=make_distribution_id(),
            dataset_id=ds.id,
            dist_type="upload",
            access_url=None,
            download_url="public/x/file.csv",
            media_type="text/csv",
            checksum_sha256="abc",
            byte_size=10,
        )
        db.add(dist)
        await db.flush()

    return version


async def test_fair_score_empty_metadata_low(db):
    version = await _make_version(
        db,
        title="",
        description="short",
        keywords=[],
        theme=None,
    )
    score = await compute_fair_score(db, version)
    assert score.score < 0.4
    assert "findable" in score.dimensions
    assert score.dimensions["findable"].score == 0.0
    assert score.suggestions  # has suggestions to improve


async def test_fair_score_well_described_resource(db):
    version = await _make_version(
        db,
        with_distribution=True,
        license_id="CC-BY-4.0",
        language="en",
        provenance=(
            "Collected by automated sampling at the EUSC group lab using a "
            "Gamry FRA at 25C."
        ),
        rights_statement="Cite this dataset when reusing.",
    )
    score = await compute_fair_score(db, version)
    assert score.score >= 0.6
    assert score.dimensions["interoperable"].checks["has_license"]
    assert score.dimensions["accessible"].checks["has_distribution"]


async def test_fair_score_publisher_resolves_with_profile(db):
    from app.models.user import UserProfile

    profile = UserProfile(sub="owner-1", display_name="Owner")
    db.add(profile)
    await db.flush()

    version = await _make_version(
        db,
        with_distribution=True,
        license_id="MIT",
        language="en",
        provenance="Provenance long enough text to count.",
        rights_statement="Cite please.",
    )
    score = await compute_fair_score(db, version)
    assert score.dimensions["interoperable"].checks["publisher_resolvable"]


async def test_fair_dimension_score_calculation(db):
    version = await _make_version(
        db,
        title="A title",
        description="A" * 60,
        keywords=["k1", "k2"],
        theme="Electrochemistry",
        doi=None,
    )
    score = await compute_fair_score(db, version)
    # findable: 4/5 pass (no DOI)
    assert score.dimensions["findable"].score == 0.8
