"""production indexes (phase 5)

Revision ID: 0003_production_indexes
Revises: 0002_search_indexes
Create Date: 2026-05-20 00:02:00

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_production_indexes"
down_revision: Union[str, None] = "0002_search_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_resource_scope_current "
        "ON resource (scope, current_version_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rv_theme "
        "ON resource_version (theme)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rv_license "
        "ON resource_version (license_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rv_issued "
        "ON resource_version (issued DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rv_access_rights "
        "ON resource_version USING GIN (access_rights)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rv_state "
        "ON resource_version (state)"
    )

    # HNSW index for semantic similarity (requires pgvector >= 0.5)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rv_embedding "
        "ON resource_version USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for idx in (
        "idx_rv_embedding",
        "idx_rv_state",
        "idx_rv_access_rights",
        "idx_rv_issued",
        "idx_rv_license",
        "idx_rv_theme",
        "idx_resource_scope_current",
    ):
        op.execute(f"DROP INDEX IF EXISTS {idx}")
