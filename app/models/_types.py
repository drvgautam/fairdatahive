from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector as _PGVector
except Exception:  # pragma: no cover - fallback path for environments without pgvector
    _PGVector = None  # type: ignore[assignment]


class StringArray(TypeDecorator):
    """ARRAY(String) on PostgreSQL, JSON list on other dialects (e.g. SQLite tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return list(value)


class EmbeddingVector(TypeDecorator):
    """Vector(dim) on PostgreSQL via pgvector, JSON list on other dialects.

    Implemented as a TypeDecorator so DDL compilation works on non-PG dialects
    (e.g. SQLite for tests) — semantic search obviously only works on PG, but
    the column itself is a JSON list there.
    """

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and _PGVector is not None:
            return dialect.type_descriptor(_PGVector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            import json

            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                return None
        return list(value)


def vector_column_type(dim: int) -> Any:
    return EmbeddingVector(dim)


__all__ = ["StringArray", "EmbeddingVector", "vector_column_type"]
