"""SQLAlchemy 2.0 declarative models — implements DESIGN.md §3.2 Table Design.

Four entities: repos, chunks, symbols, edges. All scoped by `repo_id` for
multi-tenancy (NFR-3). Vectors and the call graph live in the same PostgreSQL
instance via pgvector.

Indexes (HNSW on `chunks.embedding`, GIN on `chunks.tsv`, the reverse edge
index, etc.) are created in the Alembic migration rather than declared here,
because they require pgvector-specific operator classes that SQLAlchemy's
Index() does not express portably.
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dcode_shared.settings import shared_settings

# ---------------------------------------------------------------------------
# Postgres ENUM types (must match the literals in dcode_shared.schemas)
# ---------------------------------------------------------------------------

repo_status_enum = SAEnum(
    "queued",
    "cloning",
    "parsing",
    "embedding",
    "graphing",
    "ready",
    "failed",
    name="repo_status",
)

chunk_type_enum = SAEnum(
    "function",
    "method",
    "class",
    "module_doc",
    name="chunk_type",
)

symbol_kind_enum = SAEnum(
    "function",
    "class",
    "method",
    "module",
    name="symbol_kind",
)

edge_type_enum = SAEnum(
    "calls",
    "imports",
    "inherits",
    "references",
    name="edge_type",
)


class Base(DeclarativeBase):
    """Declarative base for every Dcode ORM model."""


# ---------------------------------------------------------------------------
# repos
# ---------------------------------------------------------------------------


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(repo_status_enum, nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    symbols: Mapped[list["Symbol"]] = relationship(back_populates="repo", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# chunks
# ---------------------------------------------------------------------------


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repos.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_type: Mapped[str] = mapped_column(chunk_type_enum, nullable=False)
    parent_symbol: Mapped[str | None] = mapped_column(Text)
    symbol_name: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    imports: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(shared_settings.embedding_dim))
    tsv: Mapped[Any] = mapped_column(TSVECTOR)

    repo: Mapped[Repo] = relationship(back_populates="chunks")
    symbol_back_refs: Mapped[list["Symbol"]] = relationship(back_populates="chunk")


# ---------------------------------------------------------------------------
# symbols (call-graph nodes)
# ---------------------------------------------------------------------------


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repos.id", ondelete="CASCADE"),
        nullable=False,
    )
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(symbol_kind_enum, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="SET NULL"),
    )

    repo: Mapped[Repo] = relationship(back_populates="symbols")
    chunk: Mapped[Chunk | None] = relationship(back_populates="symbol_back_refs")


# ---------------------------------------------------------------------------
# edges (call-graph edges)
# ---------------------------------------------------------------------------


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repos.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type: Mapped[str] = mapped_column(edge_type_enum, nullable=False)
    source_line: Mapped[int] = mapped_column(Integer, nullable=False)
