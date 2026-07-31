"""Merge the BM25 corpus revision and historical index-run branches.

Revision ID: 004_merge_bm25_and_index_runs
Revises: 002_bm25_index_revision, 003_nonzero_embedding_count
Create Date: 2026-07-30
"""

from collections.abc import Sequence

revision: str = "004_merge_bm25_and_index_runs"
down_revision: tuple[str, str] = (
    "002_bm25_index_revision",
    "003_nonzero_embedding_count",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
