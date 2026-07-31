"""Internal retrieval and graph-query endpoints."""

import ast
import builtins
import logging
import textwrap
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from dcode_shared.db.models import Chunk as ChunkRow
from dcode_shared.db.models import Edge, Repo, Symbol
from dcode_shared.embedding import EmbeddingClient, create_embedding_client
from dcode_shared.internal import INTERNAL_API_KEY_HEADER
from dcode_shared.reranker import RerankerClient, create_reranker_client
from dcode_shared.schemas import (
    CallDirection,
    CallNeighbors,
    Chunk,
    Location,
    ScoreComponents,
    SourceCall,
)
from dcode_shared.symbols import select_symbol_matches
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from dcode_api.deps import get_db
from dcode_api.retrieval.bm25 import search_repo_bm25
from dcode_api.settings import api_settings

logger = logging.getLogger(__name__)


async def _require_internal_api_key(
    x_dcode_internal_key: str | None = Header(default=None, alias=INTERNAL_API_KEY_HEADER),
) -> None:
    if x_dcode_internal_key != api_settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "internal route requires service auth"},
        )


router = APIRouter(tags=["internal"], dependencies=[Depends(_require_internal_api_key)])

_SEARCH_CANDIDATE_LIMIT = 50
_RRF_K = 60
# Cap per-passage length sent to the reranker. BGE on CPU is token-bound: full
# chunk bodies (up to max_chunk_chars) push a 10-passage rerank past 40s, while
# short passages finish in ~1s. The symbol name + path + opening lines carry the
# ranking signal, so this keeps rerank interactive without losing quality.
_RERANK_PASSAGE_CHARS = 256
_REFERENCE_EDGE_TYPES = ("calls", "references")
_MODULE_REFERENCE_EDGE_TYPES = ("calls", "references", "imports")
_BUILTIN_CALL_NAMES = frozenset(dir(builtins))
_ROUTINE_CONTAINER_METHODS = frozenset(
    {
        "add",
        "append",
        "clear",
        "copy",
        "discard",
        "extend",
        "get",
        "insert",
        "items",
        "keys",
        "pop",
        "remove",
        "setdefault",
        "sort",
        "update",
        "values",
    }
)


@dataclass(frozen=True)
class SearchCandidate:
    row: ChunkRow
    sparse_score: float = 0.0
    dense_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: float = 0.0


@router.get("/search", response_model=list[Chunk])
async def search(
    repo_id: UUID,
    query: str = Query(..., min_length=1),
    k: int = Query(10, ge=1, le=50),
    mode: str = Query("hybrid", pattern="^(sparse|dense|hybrid)$"),
    db: AsyncSession = Depends(get_db),
) -> list[Chunk]:
    repo = await _require_repo(db, repo_id)
    return await _search_chunks(
        db,
        repo_id,
        query,
        k,
        mode=mode,
        index_revision=int(repo.index_revision or 0),
    )


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


@router.get("/get_call_neighbors", response_model=CallNeighbors)
async def get_call_neighbors(
    repo_id: UUID,
    symbol: str = Query(..., min_length=1),
    direction: CallDirection = Query("both"),
    db: AsyncSession = Depends(get_db),
) -> CallNeighbors:
    """Return directed call edges plus source expressions with unresolved targets."""
    await _require_repo(db, repo_id)
    return await _get_call_neighbors(db, repo_id, symbol, direction)


@router.get("/get_dependencies", response_model=list[Location])
async def get_dependencies(
    repo_id: UUID,
    module: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[Location]:
    await _require_repo(db, repo_id)
    return await _get_dependencies(db, repo_id, module)


@router.get("/get_dependents", response_model=list[Location])
async def get_dependents(
    repo_id: UUID,
    module: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[Location]:
    await _require_repo(db, repo_id)
    return await _get_dependents(db, repo_id, module)


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


async def _search_chunks(
    db: AsyncSession,
    repo_id: UUID,
    query: str,
    k: int,
    *,
    mode: str = "hybrid",
    index_revision: int = 0,
) -> list[Chunk]:
    query_text = query.strip()
    if not query_text:
        return []

    candidate_limit = max(k, _SEARCH_CANDIDATE_LIMIT)

    if mode == "sparse":
        sparse = await _search_sparse_candidates(
            db,
            repo_id,
            query_text,
            index_revision=index_revision,
            limit=candidate_limit,
        )
        reranked = _identity_rerank(sparse)
        return [_chunk_from_candidate(c) for c in reranked[:k]]

    query_vector = await _embed_search_query(query_text)

    if mode == "dense":
        dense = await _search_dense_candidates(db, repo_id, query_vector, limit=candidate_limit)
        # Degrade to sparse when stub embeddings are active (no query vector).
        if not dense:
            sparse = await _search_sparse_candidates(
                db,
                repo_id,
                query_text,
                index_revision=index_revision,
                limit=candidate_limit,
            )
            reranked = _identity_rerank(sparse)
        else:
            reranked = _identity_rerank(dense)
        return [_chunk_from_candidate(c) for c in reranked[:k]]

    # mode == "hybrid": sparse + dense → RRF fusion → rerank
    sparse = await _search_sparse_candidates(
        db,
        repo_id,
        query_text,
        index_revision=index_revision,
        limit=candidate_limit,
    )
    dense = await _search_dense_candidates(db, repo_id, query_vector, limit=candidate_limit)
    fused = _fuse_search_candidates(sparse, dense)
    reranked = await _rerank_candidates(query_text, fused)
    return [_chunk_from_candidate(candidate) for candidate in reranked[:k]]


async def _search_sparse_candidates(
    db: AsyncSession,
    repo_id: UUID,
    query: str,
    *,
    index_revision: int,
    limit: int,
) -> list[SearchCandidate]:
    return [
        SearchCandidate(row=row, sparse_score=score)
        for row, score in await search_repo_bm25(
            db,
            repo_id,
            query,
            index_revision=index_revision,
            limit=limit,
        )
    ]


async def _search_dense_candidates(
    db: AsyncSession,
    repo_id: UUID,
    query_vector: Sequence[float] | None,
    *,
    limit: int,
) -> list[SearchCandidate]:
    # Stub embedding mode deliberately degrades to sparse-only until a real
    # query embedder is wired into the API.
    if query_vector is None:
        return []

    distance = ChunkRow.embedding.cosine_distance(list(query_vector))
    stmt = (
        select(ChunkRow, (1.0 - distance).label("dense_score"))
        .where(ChunkRow.repo_id == repo_id)
        .where(ChunkRow.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    result = await db.execute(stmt)
    candidates: list[SearchCandidate] = []
    for row, dense_score in result.all():
        candidates.append(SearchCandidate(row=row, dense_score=float(dense_score)))
    return candidates


_query_embedding_client: EmbeddingClient | None = None


def _get_query_embedding_client() -> EmbeddingClient:
    global _query_embedding_client
    if _query_embedding_client is None:
        _query_embedding_client = create_embedding_client(
            model=api_settings.embedding_model,
            dim=api_settings.embedding_dim,
            endpoint=api_settings.embedding_endpoint,
            batch_size=api_settings.embedding_batch_size,
            max_retries=api_settings.embedding_max_retries,
        )
    return _query_embedding_client


async def _embed_search_query(query: str) -> list[float] | None:
    if api_settings.embedding_model == "stub":
        return None

    vectors = await _get_query_embedding_client().embed_batch([query])
    if not vectors:
        return None
    return vectors[0]


_query_reranker_client: RerankerClient | None = None
_query_reranker_client_initialized = False


def _get_query_reranker_client() -> RerankerClient | None:
    global _query_reranker_client, _query_reranker_client_initialized
    if not _query_reranker_client_initialized:
        _query_reranker_client = create_reranker_client(
            model=api_settings.reranker_model,
            endpoint=api_settings.reranker_endpoint,
            max_retries=api_settings.reranker_max_retries,
        )
        _query_reranker_client_initialized = True
    return _query_reranker_client


def _passage_text(candidate: SearchCandidate) -> str:
    row = candidate.row
    return f"{row.symbol_name}\n{row.file_path}\n{row.content[:_RERANK_PASSAGE_CHARS]}"


async def _rerank_candidates(
    query: str,
    candidates: list[SearchCandidate],
) -> list[SearchCandidate]:
    if not candidates:
        return []

    reranker = _get_query_reranker_client()
    if reranker is None:
        return _identity_rerank(candidates)

    pool = sorted(
        candidates,
        key=lambda candidate: (
            candidate.fused_score,
            candidate.sparse_score,
            candidate.dense_score,
            candidate.row.file_path,
            candidate.row.start_line,
        ),
        reverse=True,
    )[: api_settings.reranker_candidate_limit]
    passages = [_passage_text(candidate) for candidate in pool]
    try:
        scores = await reranker.rerank(query, passages)
    except Exception as exc:  # noqa: BLE001 — a slow/unavailable reranker degrades ranking, not the whole search
        logger.warning("reranker unavailable; falling back to fused (RRF) order: %s", exc)
        return _identity_rerank(candidates)
    reranked = [
        SearchCandidate(
            row=candidate.row,
            sparse_score=candidate.sparse_score,
            dense_score=candidate.dense_score,
            fused_score=candidate.fused_score,
            rerank_score=score,
        )
        for candidate, score in zip(pool, scores, strict=True)
    ]
    return sorted(
        reranked,
        key=lambda candidate: (
            candidate.rerank_score,
            candidate.fused_score,
            candidate.sparse_score,
            candidate.dense_score,
            candidate.row.file_path,
            candidate.row.start_line,
        ),
        reverse=True,
    )


def _fuse_search_candidates(
    sparse: list[SearchCandidate],
    dense: list[SearchCandidate],
    *,
    dense_weight: float | None = None,
    sparse_weight: float | None = None,
) -> list[SearchCandidate]:
    dense_w = api_settings.rrf_dense_weight if dense_weight is None else dense_weight
    sparse_w = api_settings.rrf_sparse_weight if sparse_weight is None else sparse_weight

    by_chunk_id: dict[UUID, SearchCandidate] = {}
    sparse_ranks = {candidate.row.id: index + 1 for index, candidate in enumerate(sparse)}
    dense_ranks = {candidate.row.id: index + 1 for index, candidate in enumerate(dense)}

    for candidate in sparse:
        by_chunk_id[candidate.row.id] = candidate

    for candidate in dense:
        existing = by_chunk_id.get(candidate.row.id)
        if existing is None:
            by_chunk_id[candidate.row.id] = candidate
            continue
        by_chunk_id[candidate.row.id] = SearchCandidate(
            row=existing.row,
            sparse_score=existing.sparse_score,
            dense_score=candidate.dense_score,
        )

    fused: list[SearchCandidate] = []
    for chunk_id, candidate in by_chunk_id.items():
        fused_score = 0.0
        sparse_rank = sparse_ranks.get(chunk_id)
        dense_rank = dense_ranks.get(chunk_id)
        if sparse_rank is not None:
            fused_score += sparse_w * _rrf_score(sparse_rank)
        if dense_rank is not None:
            fused_score += dense_w * _rrf_score(dense_rank)
        fused.append(
            SearchCandidate(
                row=candidate.row,
                sparse_score=candidate.sparse_score,
                dense_score=candidate.dense_score,
                fused_score=fused_score,
            )
        )

    # Prefer dense_score as tie-breaker so hybrid does not demote strong
    # semantic hits when fused scores are close.
    return sorted(
        fused,
        key=lambda candidate: (
            candidate.fused_score,
            candidate.dense_score,
            candidate.sparse_score,
            candidate.row.file_path,
            candidate.row.start_line,
        ),
        reverse=True,
    )


def _identity_rerank(candidates: list[SearchCandidate]) -> list[SearchCandidate]:
    return [
        SearchCandidate(
            row=candidate.row,
            sparse_score=candidate.sparse_score,
            dense_score=candidate.dense_score,
            fused_score=candidate.fused_score,
            rerank_score=(
                candidate.fused_score
                if candidate.fused_score != 0.0
                else (
                    candidate.dense_score
                    if candidate.dense_score != 0.0
                    else candidate.sparse_score
                )
            ),
        )
        for candidate in candidates
    ]


def _rrf_score(rank: int) -> float:
    return 1.0 / (_RRF_K + rank)


def _chunk_from_candidate(candidate: SearchCandidate) -> Chunk:
    return Chunk(
        chunk_id=candidate.row.id,
        file_path=candidate.row.file_path,
        symbol_name=candidate.row.symbol_name,
        start_line=candidate.row.start_line,
        end_line=candidate.row.end_line,
        content=candidate.row.content,
        score=candidate.rerank_score,
        score_components=ScoreComponents(
            dense=candidate.dense_score,
            sparse=candidate.sparse_score,
            rerank=candidate.rerank_score,
        ),
    )


async def _find_definitions(db: AsyncSession, repo_id: UUID, symbol: str) -> list[Location]:
    rows = await _resolve_symbols(db, repo_id, symbol)
    return [_location_from_symbol(row) for row in rows]


async def _find_references(db: AsyncSession, repo_id: UUID, symbol: str) -> list[Location]:
    targets = await _resolve_symbols(db, repo_id, symbol)
    if not targets:
        return []

    edge_types = _reference_edge_types(targets)
    source_symbol = aliased(Symbol)
    stmt = (
        select(source_symbol)
        .join(Edge, Edge.source_id == source_symbol.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.edge_type.in_(edge_types))
        .where(Edge.target_id.in_([row.id for row in targets]))
        .order_by(source_symbol.file_path, source_symbol.line, source_symbol.qualified_name)
    )
    result = await db.execute(stmt)
    return _unique_locations(_location_from_symbol(row) for row in result.scalars().all())


async def _get_call_neighbors(
    db: AsyncSession,
    repo_id: UUID,
    symbol: str,
    direction: CallDirection,
) -> CallNeighbors:
    matches = await _resolve_symbols(db, repo_id, symbol)
    if not matches:
        return CallNeighbors(
            found=False,
            symbol=symbol,
            direction=direction,
        )

    symbol_ids = [row.id for row in matches]
    callers = (
        await _call_edge_neighbors(db, repo_id, symbol_ids, incoming=True)
        if direction in {"callers", "both"}
        else []
    )
    callees = (
        await _call_edge_neighbors(db, repo_id, symbol_ids, incoming=False)
        if direction in {"callees", "both"}
        else []
    )
    source_calls = (
        await _source_calls_for_matches(db, repo_id, matches)
        if direction in {"callees", "both"}
        else []
    )
    return CallNeighbors(
        found=True,
        symbol=symbol,
        direction=direction,
        matches=[_location_from_symbol(row) for row in matches],
        callers=callers,
        callees=callees,
        source_calls=source_calls,
    )


async def _call_edge_neighbors(
    db: AsyncSession,
    repo_id: UUID,
    symbol_ids: Sequence[UUID],
    *,
    incoming: bool,
) -> list[Location]:
    """Return callers (incoming) or callees (outgoing) across ``calls`` edges."""
    other_symbol = aliased(Symbol)
    join_column = Edge.source_id if incoming else Edge.target_id
    match_column = Edge.target_id if incoming else Edge.source_id
    stmt = (
        select(other_symbol)
        .join(Edge, join_column == other_symbol.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.edge_type == "calls")
        .where(match_column.in_(symbol_ids))
        .order_by(
            other_symbol.file_path,
            other_symbol.line,
            other_symbol.qualified_name,
        )
    )
    result = await db.execute(stmt)
    return _unique_locations(_location_from_symbol(row) for row in result.scalars().all())


async def _source_calls_for_matches(
    db: AsyncSession,
    repo_id: UUID,
    matches: Sequence[Symbol],
) -> list[SourceCall]:
    resolved_by_source = await _resolved_call_targets_by_source_line(
        db,
        repo_id,
        [match.id for match in matches],
    )
    source_calls: list[SourceCall] = []
    for match in matches:
        if match.chunk_id is None:
            continue
        chunk = await db.get(ChunkRow, match.chunk_id)
        if chunk is None:
            continue
        source_calls.extend(
            _extract_source_calls(
                chunk.content,
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                resolved_targets_by_line=resolved_by_source.get(match.id, {}),
            )
        )
    return _unique_source_calls(source_calls)


async def _resolved_call_targets_by_source_line(
    db: AsyncSession,
    repo_id: UUID,
    source_ids: Sequence[UUID],
) -> dict[UUID, dict[int, list[Location]]]:
    target_symbol = aliased(Symbol)
    stmt = (
        select(Edge.source_id, Edge.source_line, target_symbol)
        .join(target_symbol, Edge.target_id == target_symbol.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.edge_type == "calls")
        .where(Edge.source_id.in_(source_ids))
        .order_by(
            Edge.source_id,
            Edge.source_line,
            target_symbol.qualified_name,
        )
    )
    result = await db.execute(stmt)
    grouped: dict[UUID, dict[int, list[Location]]] = {}
    for source_id, source_line, target in result.all():
        by_line = grouped.setdefault(source_id, {})
        by_line.setdefault(int(source_line), []).append(_location_from_symbol(target))
    return grouped


def _extract_source_calls(
    content: str,
    *,
    file_path: str,
    start_line: int,
    resolved_targets_by_line: Mapping[int, Sequence[Location]],
) -> list[SourceCall]:
    try:
        tree = ast.parse(textwrap.dedent(content))
    except SyntaxError:
        return []

    call_nodes = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.Call)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    source_calls: list[SourceCall] = []
    for node in call_nodes:
        expression = ast.unparse(node.func)
        terminal = _call_terminal(node.func)
        line = start_line + node.lineno - 1
        resolved_target = _resolved_target_for(
            terminal,
            resolved_targets_by_line.get(line, ()),
        )
        if resolved_target is None and not _is_meaningful_unresolved_call(node.func, terminal):
            continue
        source_calls.append(
            SourceCall(
                expression=expression,
                file_path=file_path,
                line=line,
                resolved_target=resolved_target,
            )
        )
    return source_calls


def _call_terminal(function: ast.expr) -> str:
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _resolved_target_for(
    terminal: str,
    targets: Sequence[Location],
) -> Location | None:
    matches = [target for target in targets if target.symbol.rsplit(".", 1)[-1] == terminal]
    return matches[0] if len(matches) == 1 else None


def _is_meaningful_unresolved_call(function: ast.expr, terminal: str) -> bool:
    if not terminal:
        return False
    if isinstance(function, ast.Name):
        return terminal not in _BUILTIN_CALL_NAMES
    if isinstance(function, ast.Attribute):
        return terminal not in _ROUTINE_CONTAINER_METHODS
    return False


def _unique_source_calls(source_calls: Iterable[SourceCall]) -> list[SourceCall]:
    unique: list[SourceCall] = []
    seen: set[tuple[str, str, int, str | None]] = set()
    for source_call in source_calls:
        target = source_call.resolved_target
        key = (
            source_call.expression,
            source_call.file_path,
            source_call.line,
            target.symbol if target is not None else None,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(source_call)
    return unique


async def _get_dependencies(db: AsyncSession, repo_id: UUID, module: str) -> list[Location]:
    sources = await _resolve_symbols(db, repo_id, module, module_only=True)
    if not sources:
        return []

    target_symbol = aliased(Symbol)
    stmt = (
        select(target_symbol)
        .join(Edge, Edge.target_id == target_symbol.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.edge_type == "imports")
        .where(Edge.source_id.in_([row.id for row in sources]))
        .order_by(target_symbol.file_path, target_symbol.line, target_symbol.qualified_name)
    )
    result = await db.execute(stmt)
    return _unique_locations(_location_from_symbol(row) for row in result.scalars().all())


async def _get_dependents(db: AsyncSession, repo_id: UUID, module: str) -> list[Location]:
    """Reverse of _get_dependencies: the modules that import the given module.

    Backed by the reverse edge index ix_edges_target (repo_id, target_id, edge_type).
    """
    targets = await _resolve_symbols(db, repo_id, module, module_only=True)
    if not targets:
        return []

    source_symbol = aliased(Symbol)
    stmt = (
        select(source_symbol)
        .join(Edge, Edge.source_id == source_symbol.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.edge_type == "imports")
        .where(Edge.target_id.in_([row.id for row in targets]))
        .order_by(source_symbol.file_path, source_symbol.line, source_symbol.qualified_name)
    )
    result = await db.execute(stmt)
    return _unique_locations(_location_from_symbol(row) for row in result.scalars().all())


async def _get_file_outline(db: AsyncSession, repo_id: UUID, path: str) -> list[Location]:
    stmt = (
        select(Symbol)
        .where(Symbol.repo_id == repo_id)
        .where(Symbol.file_path == path)
        .order_by(Symbol.file_path, Symbol.line, Symbol.qualified_name)
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

    stmt = base_stmt.order_by(Symbol.qualified_name, Symbol.file_path, Symbol.line)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return _select_symbol_matches(rows, symbol)


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


def _select_symbol_matches(rows: Sequence[Symbol], symbol: str) -> list[Symbol]:
    """Thin alias over the shared rule.

    The body moved to `dcode_shared.symbols` because the agent's groundedness
    guardrail has to apply the same rule, and it was applying a stricter one — so
    the tool here accepted a name the guardrail then rejected. Kept as a named
    function rather than inlining the import at each call site, so the several
    callers below read unchanged.
    """
    return select_symbol_matches(rows, symbol)


def _reference_edge_types(targets: Sequence[Symbol]) -> tuple[str, ...]:
    if any(target.kind == "module" for target in targets):
        return _MODULE_REFERENCE_EDGE_TYPES
    return _REFERENCE_EDGE_TYPES
