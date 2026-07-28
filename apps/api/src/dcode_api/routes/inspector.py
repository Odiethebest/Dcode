"""Read-only source + call-graph inspector endpoints (Phase 2 workbench).

Postgres-only, scoped by `repo_id`, no agent involvement. On a cited
`file:line` these locate the AST chunk that spans the line; when a line falls
outside every chunk they degrade (the cited symbol's chunk → the file outline
→ an honest empty state) rather than 500, so clicking a citation always shows
something.
"""

from collections.abc import Iterable
from typing import Literal
from uuid import UUID

from dcode_shared.db.models import Chunk, Edge, Repo, Symbol
from dcode_shared.schemas import Location, SourceResponse, SymbolNeighbors
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from dcode_api.deps import get_db

router = APIRouter(tags=["inspector"])

_CALL_EDGE = "calls"
_REFERENCE_EDGE = "references"


@router.get("/repos/{repo_id}/source", response_model=SourceResponse)
async def get_source(
    repo_id: UUID,
    file_path: str | None = Query(default=None),
    line: int | None = Query(default=None, ge=1),
    symbol: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Resolve the source behind a cited `file:line` (with graceful fallback)."""
    await _require_repo(db, repo_id)
    return await _resolve_source(db, repo_id, file_path, line, symbol)


@router.get("/repos/{repo_id}/neighbors", response_model=SymbolNeighbors)
async def get_neighbors(
    repo_id: UUID,
    symbol: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> SymbolNeighbors:
    """Return call-graph neighbors (called-by / calls / references) for a symbol."""
    await _require_repo(db, repo_id)
    return await _resolve_neighbors(db, repo_id, symbol)


async def _require_repo(db: AsyncSession, repo_id: UUID) -> Repo:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPO_NOT_FOUND", "message": f"Unknown repo_id: {repo_id}"},
        )
    return repo


# ---------------------------------------------------------------------------
# source
# ---------------------------------------------------------------------------


async def _resolve_source(
    db: AsyncSession,
    repo_id: UUID,
    file_path: str | None,
    line: int | None,
    symbol: str | None,
) -> SourceResponse:
    # 1) The chunk that spans the cited line — the happy path. Every verified
    #    file:line citation is chunk-backed by construction (the groundedness
    #    check only verifies a line a chunk covers).
    if file_path and line is not None:
        chunk = await _chunk_containing(db, repo_id, file_path, line)
        if chunk is not None:
            return _source_from_chunk(chunk, cited_line=line, granularity="chunk")

    # 2) Degrade to the cited symbol's own chunk (line outside any chunk, or a
    #    bare symbol citation with no line).
    if symbol:
        sym = await _resolve_symbol(db, repo_id, symbol)
        if sym is not None:
            if sym.chunk_id is not None:
                chunk = await db.get(Chunk, sym.chunk_id)
                if chunk is not None:
                    return _source_from_chunk(
                        chunk, cited_line=line or sym.line, granularity="symbol_chunk"
                    )
            # 3) Symbol has no chunk → the file outline around it.
            outline = await _file_outline(db, repo_id, sym.file_path)
            if outline:
                return SourceResponse(
                    found=True,
                    granularity="file_outline",
                    file_path=sym.file_path,
                    symbol_name=sym.qualified_name,
                    cited_line=line or sym.line,
                    outline=outline,
                )

    # 4) Nothing indexed at this granularity — an honest empty state, not a 500.
    return SourceResponse(
        found=False,
        granularity="none",
        file_path=file_path,
        symbol_name=symbol,
        cited_line=line,
    )


async def _chunk_containing(
    db: AsyncSession, repo_id: UUID, file_path: str, line: int
) -> Chunk | None:
    stmt = (
        select(Chunk)
        .where(Chunk.repo_id == repo_id)
        .where(Chunk.file_path == file_path)
        .where(Chunk.start_line <= line)
        .where(Chunk.end_line >= line)
        # Tightest span first, so a nested method wins over its enclosing class.
        .order_by(Chunk.end_line - Chunk.start_line)
        .limit(1)
    )
    chunk: Chunk | None = await db.scalar(stmt)
    return chunk


def _source_from_chunk(
    chunk: Chunk,
    *,
    cited_line: int | None,
    granularity: Literal["chunk", "symbol_chunk"],
) -> SourceResponse:
    return SourceResponse(
        found=True,
        granularity=granularity,
        file_path=chunk.file_path,
        symbol_name=chunk.symbol_name,
        chunk_type=chunk.chunk_type,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        cited_line=cited_line,
        content=chunk.content,
    )


# ---------------------------------------------------------------------------
# neighbors
# ---------------------------------------------------------------------------


async def _resolve_neighbors(db: AsyncSession, repo_id: UUID, symbol: str) -> SymbolNeighbors:
    sym = await _resolve_symbol(db, repo_id, symbol)
    if sym is None:
        return SymbolNeighbors(found=False, symbol=symbol)

    return SymbolNeighbors(
        found=True,
        symbol=sym.qualified_name,
        file_path=sym.file_path,
        line=sym.line,
        called_by=await _edge_neighbors(db, repo_id, sym.id, _CALL_EDGE, incoming=True),
        calls=await _edge_neighbors(db, repo_id, sym.id, _CALL_EDGE, incoming=False),
        references=await _edge_neighbors(db, repo_id, sym.id, _REFERENCE_EDGE, incoming=True),
    )


async def _edge_neighbors(
    db: AsyncSession,
    repo_id: UUID,
    symbol_id: UUID,
    edge_type: str,
    *,
    incoming: bool,
) -> list[Location]:
    """Neighbors across one edge type.

    incoming=True  → symbols pointing AT this one (callers / referrers).
    incoming=False → symbols this one points at (callees).
    """
    other = aliased(Symbol)
    # Incoming: join the edge source (the caller) and match on target = symbol.
    # Outgoing: join the edge target (the callee) and match on source = symbol.
    join_col = Edge.source_id if incoming else Edge.target_id
    match_col = Edge.target_id if incoming else Edge.source_id
    stmt = (
        select(other)
        .join(Edge, join_col == other.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.edge_type == edge_type)
        .where(match_col == symbol_id)
        .order_by(other.file_path, other.line, other.qualified_name)
    )
    result = await db.execute(stmt)
    return _unique_locations(_location_from_symbol(row) for row in result.scalars().all())


# ---------------------------------------------------------------------------
# shared symbol resolution
# ---------------------------------------------------------------------------


async def _resolve_symbol(db: AsyncSession, repo_id: UUID, symbol: str) -> Symbol | None:
    """Exact qualified-name match, else a suffix match (mirrors internal routes)."""
    exact: Symbol | None = await db.scalar(
        select(Symbol)
        .where(Symbol.repo_id == repo_id)
        .where(Symbol.qualified_name == symbol)
        .limit(1)
    )
    if exact is not None:
        return exact
    fallback: Symbol | None = await db.scalar(
        select(Symbol)
        .where(Symbol.repo_id == repo_id)
        .where(Symbol.qualified_name.endswith(f".{symbol}"))
        .order_by(Symbol.qualified_name, Symbol.file_path, Symbol.line)
        .limit(1)
    )
    return fallback


async def _file_outline(db: AsyncSession, repo_id: UUID, file_path: str) -> list[Location]:
    stmt = (
        select(Symbol)
        .where(Symbol.repo_id == repo_id)
        .where(Symbol.file_path == file_path)
        .order_by(Symbol.line, Symbol.qualified_name)
    )
    result = await db.execute(stmt)
    return [_location_from_symbol(row) for row in result.scalars().all()]


def _location_from_symbol(row: Symbol) -> Location:
    return Location(
        symbol=row.qualified_name,
        file_path=row.file_path,
        line=row.line,
        chunk_id=row.chunk_id,
    )


def _unique_locations(locations: Iterable[Location]) -> list[Location]:
    unique: list[Location] = []
    seen: set[tuple[str, str, int]] = set()
    for location in locations:
        key = (location.symbol, location.file_path, location.line)
        if key in seen:
            continue
        seen.add(key)
        unique.append(location)
    return unique
