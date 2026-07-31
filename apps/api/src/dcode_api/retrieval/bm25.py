"""Repository-scoped loading and caching for the shared BM25 scorer."""

import logging
from collections import OrderedDict
from dataclasses import dataclass
from uuid import UUID

from dcode_shared.bm25 import BM25Index, code_document_text
from dcode_shared.db.models import Chunk as ChunkRow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

logger = logging.getLogger(__name__)

_BM25_CACHE_MAX_REPOS = 8


@dataclass(frozen=True)
class _CachedCorpus:
    rows: tuple[ChunkRow, ...]
    index: BM25Index


_corpus_cache: OrderedDict[tuple[UUID, int], _CachedCorpus] = OrderedDict()


async def search_repo_bm25(
    db: AsyncSession,
    repo_id: UUID,
    query: str,
    *,
    index_revision: int,
    limit: int,
) -> list[tuple[ChunkRow, float]]:
    """Score the complete repository corpus and return deterministic top hits."""

    if limit <= 0:
        return []

    corpus = await _load_corpus(db, repo_id, index_revision)
    scores = corpus.index.scores(query)
    ranked = [(row, score) for row, score in zip(corpus.rows, scores, strict=True) if score > 0.0]
    ranked.sort(
        key=lambda hit: (
            -hit[1],
            hit[0].file_path,
            hit[0].start_line,
            str(hit[0].id),
        )
    )
    return ranked[:limit]


async def _load_corpus(
    db: AsyncSession,
    repo_id: UUID,
    index_revision: int,
) -> _CachedCorpus:
    key = (repo_id, index_revision)
    cached = _corpus_cache.get(key)
    if cached is not None:
        _corpus_cache.move_to_end(key)
        return cached

    result = await db.execute(
        select(ChunkRow)
        .options(
            load_only(
                ChunkRow.id,
                ChunkRow.repo_id,
                ChunkRow.file_path,
                ChunkRow.symbol_name,
                ChunkRow.signature,
                ChunkRow.start_line,
                ChunkRow.end_line,
                ChunkRow.content,
            )
        )
        .where(ChunkRow.repo_id == repo_id)
        .order_by(ChunkRow.file_path, ChunkRow.start_line, ChunkRow.id)
    )
    rows = tuple(result.scalars().all())
    corpus = _CachedCorpus(
        rows=rows,
        index=BM25Index(
            [
                code_document_text(
                    symbol_name=row.symbol_name,
                    file_path=row.file_path,
                    signature=row.signature,
                    content=row.content,
                )
                for row in rows
            ]
        ),
    )

    # Only one generation per repo is useful.  Removing superseded generations
    # also bounds stale ORM objects after a repository is re-indexed.
    for stale_key in [cached_key for cached_key in _corpus_cache if cached_key[0] == repo_id]:
        del _corpus_cache[stale_key]
    _corpus_cache[key] = corpus
    _corpus_cache.move_to_end(key)
    while len(_corpus_cache) > _BM25_CACHE_MAX_REPOS:
        _corpus_cache.popitem(last=False)

    logger.info(
        "built BM25 corpus repo_id=%s index_revision=%s chunks=%s",
        repo_id,
        index_revision,
        len(rows),
    )
    return corpus


def _clear_corpus_cache() -> None:
    """Clear process-local BM25 state (used by tests and controlled reloads)."""

    _corpus_cache.clear()
