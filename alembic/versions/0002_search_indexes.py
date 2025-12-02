"""full-text search index (phase 3)

Revision ID: 0002_search_indexes
Revises: 0001_initial
Create Date: 2026-05-20 00:01:00

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_search_indexes"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rv_fts
        ON resource_version
        USING GIN (
            to_tsvector(
                'english',
                COALESCE(title, '') || ' ' || COALESCE(description, '') || ' ' ||
                COALESCE(theme, '') || ' ' || COALESCE(array_to_string(keywords, ' '), '')
            )
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS idx_rv_fts")
