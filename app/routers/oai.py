from __future__ import annotations

from datetime import datetime, timezone
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.resource_service import version_relations_options

from app.config import settings
from app.core.dependencies import get_db
from app.models.dataset import Dataset
from app.models.resource import Resource, ResourceVersion
from app.models.user import UserProfile
from app.services.rdf_service import to_oai_dc, version_iri

router = APIRouter(tags=["oai-pmh"])

OAI_NAMESPACE = "http://www.openarchives.org/OAI/2.0/"
DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"
OAI_DC_NAMESPACE = "http://www.openarchives.org/OAI/2.0/oai_dc/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap_envelope(verb: str, body: str, request_url: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<OAI-PMH xmlns="{OAI_NAMESPACE}" '
        f'xmlns:xsi="{XSI}" '
        f'xsi:schemaLocation="{OAI_NAMESPACE} http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd">'
        f"<responseDate>{_utc_now()}</responseDate>"
        f'<request verb="{escape(verb)}">{escape(request_url)}</request>'
        f"{body}"
        "</OAI-PMH>"
    )


def _oai_error(verb: str, code: str, message: str, request_url: str) -> Response:
    body = f'<error code="{code}">{escape(message)}</error>'
    return Response(_wrap_envelope(verb, body, request_url), media_type="text/xml")


def _format_dc_record(rec_data: dict) -> str:
    parts: list[str] = [
        '<oai_dc:dc xmlns:oai_dc="' + OAI_DC_NAMESPACE + '" '
        'xmlns:dc="' + DC_NAMESPACE + '" '
        'xmlns:xsi="' + XSI + '" '
        'xsi:schemaLocation="' + OAI_DC_NAMESPACE + " http://www.openarchives.org/OAI/2.0/oai_dc.xsd\">"
    ]

    def add(tag: str, value):
        if value is None:
            return
        if isinstance(value, list):
            for v in value:
                if v is None:
                    continue
                parts.append(f"<dc:{tag}>{escape(str(v))}</dc:{tag}>")
        else:
            parts.append(f"<dc:{tag}>{escape(str(value))}</dc:{tag}>")

    add("identifier", rec_data.get("identifier"))
    add("title", rec_data.get("title"))
    add("description", rec_data.get("description"))
    add("creator", rec_data.get("creator"))
    add("date", rec_data.get("date"))
    add("subject", rec_data.get("subject"))
    add("rights", rec_data.get("rights"))
    add("language", rec_data.get("language"))
    add("type", rec_data.get("type"))
    add("format", rec_data.get("format"))
    parts.append("</oai_dc:dc>")
    return "".join(parts)


def _header(version: ResourceVersion) -> str:
    status = ' status="deleted"' if version.data_deleted else ""
    setspec = ""
    return (
        f"<header{status}>"
        f"<identifier>{escape(str(version_iri(version.id)))}</identifier>"
        f"<datestamp>{version.modified.strftime('%Y-%m-%dT%H:%M:%SZ') if version.modified else _utc_now()}</datestamp>"
        f"{setspec}"
        "</header>"
    )


async def _all_published(db: AsyncSession, from_: datetime | None, until: datetime | None, set_: str | None) -> list[ResourceVersion]:
    stmt = select(ResourceVersion).options(version_relations_options())
    stmt = stmt.where(ResourceVersion.state.in_(("published", "deprecated")))
    if from_:
        stmt = stmt.where(ResourceVersion.issued >= from_)
    if until:
        stmt = stmt.where(ResourceVersion.issued <= until)
    if set_:
        stmt = stmt.join(Resource, Resource.id == ResourceVersion.base_resource_id).where(
            Resource.scope == set_
        )
    stmt = stmt.order_by(ResourceVersion.issued.asc()).limit(500)
    return list((await db.execute(stmt)).scalars().all())


def _parse_iso(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/oai")
async def oai(
    request: Request,
    verb: str | None = Query(default=None),
    identifier: str | None = Query(default=None),
    metadataPrefix: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    until: str | None = Query(default=None),
    set_: str | None = Query(default=None, alias="set"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    request_url = str(request.url)

    if verb is None:
        return _oai_error("", "badVerb", "Missing verb parameter.", request_url)

    if verb == "Identify":
        body = (
            "<Identify>"
            "<repositoryName>FairDataHive</repositoryName>"
            f"<baseURL>{escape(settings.base_url.rstrip('/') + '/api/v1/oai')}</baseURL>"
            "<protocolVersion>2.0</protocolVersion>"
            "<adminEmail>admin@fairdatahive.local</adminEmail>"
            f"<earliestDatestamp>{_utc_now()}</earliestDatestamp>"
            "<deletedRecord>persistent</deletedRecord>"
            "<granularity>YYYY-MM-DDThh:mm:ssZ</granularity>"
            "</Identify>"
        )
        return Response(_wrap_envelope(verb, body, request_url), media_type="text/xml")

    if verb == "ListMetadataFormats":
        body = (
            "<ListMetadataFormats>"
            "<metadataFormat>"
            "<metadataPrefix>oai_dc</metadataPrefix>"
            "<schema>http://www.openarchives.org/OAI/2.0/oai_dc.xsd</schema>"
            "<metadataNamespace>http://www.openarchives.org/OAI/2.0/oai_dc/</metadataNamespace>"
            "</metadataFormat>"
            "<metadataFormat>"
            "<metadataPrefix>dcat</metadataPrefix>"
            "<schema>http://www.w3.org/ns/dcat</schema>"
            "<metadataNamespace>http://www.w3.org/ns/dcat#</metadataNamespace>"
            "</metadataFormat>"
            "</ListMetadataFormats>"
        )
        return Response(_wrap_envelope(verb, body, request_url), media_type="text/xml")

    if verb == "ListSets":
        scope_stmt = select(Resource.scope).distinct()
        scopes = [row[0] for row in (await db.execute(scope_stmt)).all() if row[0]]
        sets = "".join(
            f"<set><setSpec>{escape(s)}</setSpec><setName>{escape(s)}</setName></set>"
            for s in scopes
        )
        body = f"<ListSets>{sets}</ListSets>"
        return Response(_wrap_envelope(verb, body, request_url), media_type="text/xml")

    if verb in ("ListIdentifiers", "ListRecords", "GetRecord"):
        if verb in ("ListIdentifiers", "ListRecords") and metadataPrefix is None:
            return _oai_error(
                verb, "badArgument", "metadataPrefix is required.", request_url
            )

        if verb == "GetRecord":
            if identifier is None or metadataPrefix is None:
                return _oai_error(
                    verb, "badArgument", "identifier and metadataPrefix are required.",
                    request_url,
                )
            version_id = identifier.rstrip("/").rsplit("/", 1)[-1]
            stmt = (
                select(ResourceVersion)
                .where(ResourceVersion.id == version_id)
                .options(version_relations_options())
            )
            version = (await db.execute(stmt)).scalar_one_or_none()
            if version is None:
                return _oai_error(
                    verb, "idDoesNotExist", "No such record.", request_url
                )
            versions = [version]
        else:
            versions = await _all_published(
                db, _parse_iso(from_), _parse_iso(until), set_
            )

        if metadataPrefix not in ("oai_dc", "dcat"):
            return _oai_error(
                verb,
                "cannotDisseminateFormat",
                f"Unknown metadataPrefix '{metadataPrefix}'.",
                request_url,
            )

        records_xml: list[str] = []
        for v in versions:
            profile = await db.get(UserProfile, v.publisher_sub)
            metadata_xml = ""
            if not v.data_deleted:
                if metadataPrefix == "oai_dc":
                    dc_dict = to_oai_dc(
                        v, profile.display_name if profile else None
                    )
                    metadata_xml = f"<metadata>{_format_dc_record(dc_dict)}</metadata>"
                else:
                    from app.services.rdf_service import to_jsonld, version_to_graph

                    g = await version_to_graph(db, v)
                    jl = to_jsonld(g)
                    metadata_xml = (
                        "<metadata><dcat>" + escape(jl) + "</dcat></metadata>"
                    )

            if verb == "ListIdentifiers":
                records_xml.append(_header(v))
            else:
                records_xml.append(f"<record>{_header(v)}{metadata_xml}</record>")

        wrapper = (
            "ListIdentifiers"
            if verb == "ListIdentifiers"
            else "ListRecords"
            if verb == "ListRecords"
            else "GetRecord"
        )
        body = f"<{wrapper}>{''.join(records_xml)}</{wrapper}>"
        return Response(_wrap_envelope(verb, body, request_url), media_type="text/xml")

    return _oai_error(verb, "badVerb", f"Unknown verb '{verb}'.", request_url)
