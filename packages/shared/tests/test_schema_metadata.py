"""Schema metadata consistency checks for models and migrations."""

from pathlib import Path

from dcode_shared.db.models import (
    Base,
    Chunk,
    Repo,
    chunk_type_enum,
    edge_type_enum,
    repo_status_enum,
    symbol_kind_enum,
)
from dcode_shared.settings import shared_settings

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "infra"
    / "migrations"
    / "versions"
    / "001_initial_schema.py"
)
_BM25_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "infra"
    / "migrations"
    / "versions"
    / "002_bm25_index_revision.py"
)
_MIGRATION_MERGE_PATH = (
    Path(__file__).resolve().parents[3]
    / "infra"
    / "migrations"
    / "versions"
    / "004_merge_bm25_and_index_runs.py"
)


def test_model_metadata_exposes_expected_tables_and_columns() -> None:
    tables = Base.metadata.tables
    assert set(tables) == {"repos", "chunks", "symbols", "edges"}
    assert set(tables["repos"].columns.keys()) == {
        "id",
        "url",
        "commit_sha",
        "status",
        "progress",
        "error",
        "index_revision",
        "created_at",
        "updated_at",
    }
    assert set(tables["chunks"].columns.keys()) == {
        "id",
        "repo_id",
        "file_path",
        "chunk_type",
        "parent_symbol",
        "symbol_name",
        "signature",
        "start_line",
        "end_line",
        "imports",
        "content",
        "embedding",
        "tsv",
    }


def test_model_enums_match_expected_schema_literals() -> None:
    assert repo_status_enum.enums == [
        "queued",
        "cloning",
        "parsing",
        "embedding",
        "graphing",
        "ready",
        "failed",
    ]
    assert chunk_type_enum.enums == ["function", "method", "class", "module_doc"]
    assert symbol_kind_enum.enums == ["function", "class", "method", "module"]
    assert edge_type_enum.enums == ["calls", "imports", "inherits", "references"]


def test_chunk_embedding_dim_matches_shared_settings() -> None:
    assert Chunk.__table__.c.embedding.type.dim == shared_settings.embedding_dim
    assert Repo.__table__.c.status.type.enums == repo_status_enum.enums


def test_initial_migration_keeps_pgvector_bootstrap_idempotent() -> None:
    migration = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "DROP TYPE IF EXISTS edge_type" in migration


def test_bm25_migration_adds_the_repository_index_revision() -> None:
    migration = _BM25_MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'down_revision: str | None = "001_initial_schema"' in migration
    assert (
        'sa.Column("index_revision", sa.Integer(), nullable=False, server_default="0")' in migration
    )


def test_bm25_migration_merges_with_the_existing_index_run_history() -> None:
    migration = _MIGRATION_MERGE_PATH.read_text(encoding="utf-8")

    assert '"002_bm25_index_revision"' in migration
    assert '"003_nonzero_embedding_count"' in migration
