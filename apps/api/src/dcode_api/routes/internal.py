"""Internal retrieval and graph-query endpoints."""

import re
from collections.abc import Iterable
from uuid import UUID

from dcode_shared.db.models import Chunk as ChunkRow
from dcode_shared.db.models import Edge, Repo, Symbol
from dcode_shared.schemas import Chunk, Location, ScoreComponents
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from dcode_api.deps import get_db

router = APIRouter(tags=["internal"])

_TERM_SPLIT_RE = re.compile(r"\s+")


@router.get("/search", response_model=list[Chunk])
async def search(
    repo_id: UUID,
    query: str = Query(..., min_length=1),
    k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[Chunk]:
    await _require_repo(db, repo_id)
    return await _search_chunks(db, repo_id, query, k)


@router.get("/find_definition", response_model=list[Location])
async def find_definition(
    repo_id: UUID,
    symbol: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[Location]:
    await _require_repo(db, repo_id)
    return await _find_definitions(db, repo_id, symbol)


@router.get("/find_references", response_model=list[Location])
async def find_references(
    repo_id: UUID,
    symbol: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[Location]:
    await _require_repo(db, repo_id)
    return await _find_references(db, repo_id, symbol)


@router.get("/get_dependencies", response_model=list[Location])
async def get_dependencies(
    repo_id: UUID,
    module: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[Location]:
    await _require_repo(db, repo_id)
    return await _get_dependencies(db, repo_id, module)


@router.get("/get_file_outline", response_model=list[Location])
async def get_file_outline(
    repo_id: UUID,
    path: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[Location]:
    await _require_repo(db, repo_id)
    return await _get_file_outline(db, repo_id, path)


async def _require_repo(db: AsyncSession, repo_id: UUID) -> Repo:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPO_NOT_FOUND", "message": f"Unknown repo_id: {repo_id}"},
        )
    return repo


async def _search_chunks(db: AsyncSession, repo_id: UUID, query: str, k: int) -> list[Chunk]:
    query_text = query.strip()
    if not query_text:
        return []

    terms = _query_terms(query_text)
    patterns = [f"%{term}%" for term in terms]
    conditions = []
    for pattern in patterns:
        conditions.extend(
            [
                ChunkRow.symbol_name.ilike(pattern),
                ChunkRow.file_path.ilike(pattern),
                ChunkRow.content.ilike(pattern),
            ]
        )

    stmt = select(ChunkRow).where(ChunkRow.repo_id == repo_id).where(or_(*conditions))
    result = await db.execute(stmt)
    rows = result.scalars().all()
    ranked = sorted(rows, key=lambda row: _chunk_rank(row, query_text, terms), reverse=True)
    return [
        Chunk(
            chunk_id=row.id,
            file_path=row.file_path,
            symbol_name=row.symbol_name,
            start_line=row.start_line,
            end_line=row.end_line,
            content=row.content,
            score=score,
            score_components=ScoreComponents(dense=0.0, sparse=score, rerank=0.0),
        )
        for row in ranked[:k]
        for score in [_chunk_rank(row, query_text, terms)]
    ]


async def _find_definitions(db: AsyncSession, repo_id: UUID, symbol: str) -> list[Location]:
    rows = await _resolve_symbols(db, repo_id, symbol)
    return [_location_from_symbol(row) for row in rows]


async def _find_references(db: AsyncSession, repo_id: UUID, symbol: str) -> list[Location]:
    targets = await _resolve_symbols(db, repo_id, symbol)
    if not targets:
        return []

    source_symbol = aliased(Symbol)
    stmt = (
        select(source_symbol)
        .join(Edge, Edge.source_id == source_symbol.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.target_id.in_([row.id for row in targets]))
        .order_by(source_symbol.file_path, source_symbol.line, source_symbol.qualified_name)
    )
    result = await db.execute(stmt)
    return _unique_locations(_location_from_symbol(row) for row in result.scalars().all())


async def _get_dependencies(db: AsyncSession, repo_id: UUID, module: str) -> list[Location]:
    sources = await _resolve_symbols(db, repo_id, module, module_only=True)
    if not sources:
        return []

    target_symbol = aliased(Symbol)
    stmt = (
        select(target_symbol)
        .join(Edge, Edge.target_id == target_symbol.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.source_id.in_([row.id for row in sources]))
        .order_by(target_symbol.file_path, target_symbol.line, target_symbol.qualified_name)
    )
    result = await db.execute(stmt)
    return _unique_locations(_location_from_symbol(row) for row in result.scalars().all())


async def _get_file_outline(db: AsyncSession, repo_id: UUID, path: str) -> list[Location]:
    stmt = (
        select(Symbol)
        .where(Symbol.repo_id == repo_id)
        .where(Symbol.file_path == path)
        .order_by(Symbol.line, Symbol.qualified_name)
    )
    result = await db.execute(stmt)
    return [_location_from_symbol(row) for row in result.scalars().all()]


async def _resolve_symbols(
    db: AsyncSession,
    repo_id: UUID,
    symbol: str,
    *,
    module_only: bool = False,
) -> list[Symbol]:
    base_stmt = select(Symbol).where(Symbol.repo_id == repo_id)
    if module_only:
        base_stmt = base_stmt.where(Symbol.kind == "module")

    exact_stmt = base_stmt.where(Symbol.qualified_name == symbol)
    exact_result = await db.execute(exact_stmt.order_by(Symbol.file_path, Symbol.line))
    exact_rows = list(exact_result.scalars().all())
    if exact_rows:
        return exact_rows

    suffix_stmt = base_stmt.where(Symbol.qualified_name.ilike(f"%.{symbol}"))
    suffix_result = await db.execute(
        suffix_stmt.order_by(Symbol.qualified_name, Symbol.file_path, Symbol.line)
    )
    return list(suffix_result.scalars().all())


def _query_terms(query: str) -> list[str]:
    lowered = query.lower().strip()
    terms = [term for term in _TERM_SPLIT_RE.split(lowered) if term]
    if lowered not in terms:
        return [lowered, *terms]
    return terms


def _chunk_rank(row: ChunkRow, query: str, terms: list[str]) -> float:
    query_lower = query.lower()
    symbol = row.symbol_name.lower()
    path = row.file_path.lower()
    content = row.content.lower()
    score = 0.0

    if symbol == query_lower:
        score += 100.0
    if path == query_lower:
        score += 90.0
    if query_lower in symbol:
        score += 35.0
    if query_lower in path:
        score += 25.0
    if query_lower in content:
        score += 10.0

    for term in terms:
        if term in symbol:
            score += 12.0
        if term in path:
            score += 8.0
        if term in content:
            score += 4.0

    return score


def _location_from_symbol(row: Symbol) -> Location:
    return Location(
        symbol=row.qualified_name,
        file_path=row.file_path,
        line=row.line,
        chunk_id=row.chunk_id,
    )


def _unique_locations(locations: Iterable[Location]) -> list[Location]:
    unique: list[Location] = []
    seen: set[tuple[str, str, int, UUID | None]] = set()
    for location in locations:
        key = (location.symbol, location.file_path, location.line, location.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(location)
    return unique
