"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-20 00:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "user_profile",
        sa.Column("sub", sa.String(length=128), primary_key=True),
        sa.Column("display_name", sa.String(length=256)),
        sa.Column("email", sa.String(length=256)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_table(
        "resource",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("owner_sub", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("current_version_id", sa.String(length=160)),
    )
    op.create_index("ix_resource_scope", "resource", ["scope"])
    op.create_index("ix_resource_owner_sub", "resource", ["owner_sub"])

    is_pg = bind.dialect.name == "postgresql"
    keywords_type = postgresql.ARRAY(sa.String) if is_pg else sa.JSON()
    access_rights_type = postgresql.ARRAY(sa.String) if is_pg else sa.JSON()
    embedding_type = sa.dialects.postgresql.array if False else None

    op.create_table(
        "resource_version",
        sa.Column("id", sa.String(length=160), primary_key=True),
        sa.Column(
            "base_resource_id",
            sa.String(length=128),
            sa.ForeignKey("resource.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_version_id", sa.String(length=160)),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("publisher_sub", sa.String(length=128), nullable=False),
        sa.Column(
            "issued",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("theme", sa.String(length=128)),
        sa.Column("keywords", keywords_type),
        sa.Column("license_id", sa.String(length=64)),
        sa.Column("doi", sa.String(length=256)),
        sa.Column("language", sa.String(length=32)),
        sa.Column("provenance", sa.Text),
        sa.Column("rights_statement", sa.Text),
        sa.Column("spatial", sa.String(length=256)),
        sa.Column("temporal", sa.String(length=256)),
        sa.Column("assumptions", sa.Text),
        sa.Column("technique", sa.Text),
        sa.Column("post_processing", sa.Text),
        sa.Column("is_private", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("access_rights", access_rights_type),
        sa.Column("data_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("dcat_ap_report", sa.Text),
        sa.Column(
            "download_count", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
    )
    op.create_index(
        "ix_resource_version_base_resource_id",
        "resource_version",
        ["base_resource_id"],
    )
    op.create_index(
        "ix_resource_version_publisher_sub", "resource_version", ["publisher_sub"]
    )

    if is_pg:
        op.execute("ALTER TABLE resource_version ADD COLUMN embedding vector(768)")
    else:
        op.add_column("resource_version", sa.Column("embedding", sa.JSON))

    op.create_table(
        "dataset",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column(
            "resource_version_id",
            sa.String(length=160),
            sa.ForeignKey("resource_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_dataset_resource_version_id", "dataset", ["resource_version_id"])

    op.create_table(
        "distribution",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(length=128),
            sa.ForeignKey("dataset.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dist_type", sa.String(length=32), nullable=False, server_default="upload"),
        sa.Column("title", sa.String(length=512)),
        sa.Column("description", sa.Text),
        sa.Column("access_url", sa.Text),
        sa.Column("download_url", sa.Text),
        sa.Column("media_type", sa.String(length=128)),
        sa.Column("checksum_sha256", sa.String(length=80)),
        sa.Column("byte_size", sa.BigInteger),
        sa.Column(
            "issued",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_distribution_dataset_id", "distribution", ["dataset_id"])

    op.create_table(
        "data_service",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column(
            "distribution_id",
            sa.String(length=128),
            sa.ForeignKey("distribution.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("endpoint_url", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
    )

    op.create_table(
        "access_request",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "resource_version_id",
            sa.String(length=160),
            sa.ForeignKey("resource_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requester_sub", sa.String(length=128), nullable=False),
        sa.Column("owner_sub", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_access_request_resource_version_id",
        "access_request",
        ["resource_version_id"],
    )
    op.create_index("ix_access_request_owner_sub", "access_request", ["owner_sub"])
    op.create_index("ix_access_request_requester_sub", "access_request", ["requester_sub"])
    op.create_index("ix_access_request_status", "access_request", ["status"])

    op.create_table(
        "notification",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_sub", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("resource_version_id", sa.String(length=160)),
        sa.Column("related_id", sa.String(length=160)),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_notification_user_sub", "notification", ["user_sub"])
    op.create_index("ix_notification_read", "notification", ["read"])

    op.create_table(
        "download_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "distribution_id",
            sa.String(length=128),
            sa.ForeignKey("distribution.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "resource_version_id",
            sa.String(length=160),
            sa.ForeignKey("resource_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_sub", sa.String(length=128)),
        sa.Column(
            "downloaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=512)),
    )
    op.create_index("ix_download_log_distribution_id", "download_log", ["distribution_id"])
    op.create_index(
        "ix_download_log_resource_version_id", "download_log", ["resource_version_id"]
    )
    op.create_index("ix_download_log_user_sub", "download_log", ["user_sub"])
    op.create_index("ix_download_log_downloaded_at", "download_log", ["downloaded_at"])


def downgrade() -> None:
    op.drop_table("download_log")
    op.drop_table("notification")
    op.drop_table("access_request")
    op.drop_table("data_service")
    op.drop_table("distribution")
    op.drop_table("dataset")
    op.drop_table("resource_version")
    op.drop_table("resource")
    op.drop_table("user_profile")
