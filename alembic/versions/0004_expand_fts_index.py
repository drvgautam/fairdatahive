"""expand FTS index to theme and keywords

Revision ID: 0004_expand_fts
Revises: 0003_production_indexes
Create Date: 2026-05-22 00:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004_expand_fts"
down_revision: Union[str, None] = "0003_production_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS idx_rv_fts")
    op.execute(
        """
        CREATE INDEX idx_rv_fts
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
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rv_fts
        ON resource_version
        USING GIN (
            to_tsvector(
                'english',
                COALESCE(title, '') || ' ' || COALESCE(description, '')
            )
        )
        """
    )
