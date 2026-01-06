from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from rdflib import Graph

logger = logging.getLogger(__name__)

SHAPES_PATH = Path(__file__).resolve().parents[2] / "static" / "dcat_ap_shapes.ttl"


@lru_cache(maxsize=1)
def _load_shapes() -> Graph | None:
    if not SHAPES_PATH.exists():
        return None
    g = Graph()
    try:
        g.parse(SHAPES_PATH, format="turtle")
        return g
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load DCAT-AP shapes: %s", exc)
        return None


def validate_dcat_ap(data_graph: Graph) -> tuple[bool, str]:
    shapes = _load_shapes()
    if shapes is None:
        return True, "DCAT-AP shapes file not available; validation skipped."
    try:
        from pyshacl import validate

        conforms, _, results_text = validate(
            data_graph=data_graph,
            shacl_graph=shapes,
            inference="rdfs",
            abort_on_first=False,
            allow_warnings=True,
            serialize_report_graph="turtle",
        )
        if isinstance(results_text, bytes):
            results_text = results_text.decode("utf-8")
        return bool(conforms), str(results_text)
    except Exception as exc:  # pragma: no cover - validation is best-effort
        logger.warning("pyshacl validation failed: %s", exc)
        return True, f"Validation error: {exc}"
