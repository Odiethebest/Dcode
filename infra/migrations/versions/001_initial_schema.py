"""Initial schema — DESIGN.md §3.2 verbatim.

Tables: repos / chunks / symbols / edges.
Extension: pgvector (HNSW index on chunks.embedding).
Full-text: GIN index on chunks.tsv.
Reverse-edge index on edges (repo_id, target_id, edge_type) for `find_references`.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

from dcode_shared.settings import shared_settings

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- repos ---
    op.create_table(
        "repos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("commit_sha", sa.Text()),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "cloning",
                "parsing",
                "embedding",
                "graphing",
                "ready",
                "failed",
                name="repo_status",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- chunks ---
    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column(
            "chunk_type",
            sa.Enum("function", "method", "class", "module_doc", name="chunk_type"),
            nullable=False,
        ),
        sa.Column("parent_symbol", sa.Text()),
        sa.Column("symbol_name", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text()),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("imports", JSONB(), nullable=False, server_default="[]"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(shared_settings.embedding_dim)),
        sa.Column("tsv", TSVECTOR()),
    )
    op.create_index("ix_chunks_repo_file", "chunks", ["repo_id", "file_path"])
    # HNSW + GIN: pgvector operator class doesn't map to SQLAlchemy's portable
    # Index() helper, so use raw SQL.
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_chunks_tsv_gin ON chunks USING gin (tsv)")

    # --- symbols ---
    op.create_table(
        "symbols",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("function", "class", "method", "module", name="symbol_kind"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column(
            "chunk_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_symbols_repo_qname_unique",
        "symbols",
        ["repo_id", "qualified_name"],
        unique=True,
    )

    # --- edges ---
    op.create_table(
        "edges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("symbols.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            UUID(as_uuid=True),
            sa.ForeignKey("symbols.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "edge_type",
            sa.Enum("calls", "imports", "inherits", "references", name="edge_type"),
            nullable=False,
        ),
        sa.Column("source_line", sa.Integer(), nullable=False),
    )
    op.create_index("ix_edges_source", "edges", ["repo_id", "source_id", "edge_type"])
    op.create_index("ix_edges_target", "edges", ["repo_id", "target_id", "edge_type"])


def downgrade() -> None:
    op.drop_index("ix_edges_target", table_name="edges")
    op.drop_index("ix_edges_source", table_name="edges")
    op.drop_table("edges")

    op.drop_index("ix_symbols_repo_qname_unique", table_name="symbols")
    op.drop_table("symbols")

    op.execute("DROP INDEX IF EXISTS ix_chunks_tsv_gin")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.drop_index("ix_chunks_repo_file", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("repos")

    op.execute("DROP TYPE IF EXISTS edge_type")
    op.execute("DROP TYPE IF EXISTS symbol_kind")
    op.execute("DROP TYPE IF EXISTS chunk_type")
    op.execute("DROP TYPE IF EXISTS repo_status")
    # NOTE: we do NOT DROP EXTENSION vector — it may be shared with other schemas.
