from __future__ import annotations

import logging
import uuid
from datetime import datetime

import httpx

from app.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.models.resource import ResourceVersion

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return all(
        [
            settings.datacite_repo_id,
            settings.datacite_password,
            settings.datacite_doi_prefix,
        ]
    )


def _make_doi() -> str:
    suffix = uuid.uuid4().hex[:10]
    return f"{settings.datacite_doi_prefix}/fairdatahive-{suffix}"


def _build_payload(doi: str, version: ResourceVersion) -> dict:
    landing = (
        f"{settings.base_url.rstrip('/')}/api/v1/resources/{version.id}/landing"
    )
    year = (version.issued or datetime.utcnow()).year
    return {
        "data": {
            "type": "dois",
            "attributes": {
                "doi": doi,
                "url": landing,
                "event": "publish",
                "titles": [{"title": version.title or version.id}],
                "creators": [
                    {"name": version.publisher_sub, "nameType": "Personal"}
                ],
                "publisher": "FairDataHive",
                "publicationYear": year,
                "types": {
                    "resourceTypeGeneral": "Dataset",
                    "resourceType": "Dataset",
                },
                "descriptions": [
                    {
                        "description": version.description or "",
                        "descriptionType": "Abstract",
                    }
                ],
            },
        }
    }


async def mint_doi(version: ResourceVersion) -> str:
    if not _configured():
        raise ConflictError(
            "DataCite credentials are not configured.",
            error_code="datacite_not_configured",
        )

    if version.state != "published":
        raise ValidationError(
            "DOIs can only be minted for published versions.",
            error_code="version_not_published",
        )

    if version.doi:
        return version.doi

    doi = _make_doi()
    payload = _build_payload(doi, version)
    url = f"{settings.datacite_api_url.rstrip('/')}/dois"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            json=payload,
            auth=(settings.datacite_repo_id or "", settings.datacite_password or ""),
            headers={"Content-Type": "application/vnd.api+json"},
        )
    if resp.status_code >= 400:
        logger.warning("DataCite minting failed: %s %s", resp.status_code, resp.text)
        raise ValidationError(
            f"DataCite responded with {resp.status_code}: {resp.text[:300]}",
            error_code="datacite_error",
        )
    return doi
