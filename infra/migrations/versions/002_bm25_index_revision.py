"""Add an explicit generation for repository retrieval corpora.

Revision ID: 002_bm25_index_revision
Revises: 001_initial_schema
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_bm25_index_revision"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repos",
        sa.Column("index_revision", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("repos", "index_revision")
