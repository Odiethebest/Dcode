"""Repository loading, caching, and ordering tests for API-side BM25."""

import uuid
from typing import Any

import pytest
from dcode_api.retrieval import bm25
from dcode_shared.db.models import Chunk as ChunkRow


class FakeScalarResult:
    def __init__(self, rows: list[ChunkRow]) -> None:
        self.rows = rows

    def scalars(self) -> "FakeScalarResult":
        return self

    def all(self) -> list[ChunkRow]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[ChunkRow]) -> None:
        self.rows = rows
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> FakeScalarResult:
        self.statements.append(statement)
        return FakeScalarResult(self.rows)


@pytest.fixture(autouse=True)
def clear_bm25_cache() -> None:
    bm25._clear_corpus_cache()


async def test_repo_bm25_uses_code_tokens_and_raw_bm25_scores() -> None:
    repo_id = uuid.uuid4()
    auth = _chunk(
        repo_id,
        "src/requests/auth.py",
        "HTTPBasicAuth",
        10,
        "class HTTPBasicAuth: pass",
    )
    unrelated = _chunk(
        repo_id,
        "src/requests/models.py",
        "PreparedRequest",
        20,
        "class PreparedRequest: pass",
    )
    session = FakeSession([unrelated, auth])

    hits = await bm25.search_repo_bm25(
        session,  # type: ignore[arg-type]
        repo_id,
        "basic auth",
        index_revision=1,
        limit=5,
    )

    assert [row.id for row, _ in hits] == [auth.id]
    assert hits[0][1] > 0.0
    statement = session.statements[0]
    assert repo_id in statement.compile().params.values()
    assert "LIKE" not in str(statement.compile()).upper()


async def test_repo_bm25_ties_are_stable_by_location_then_id() -> None:
    repo_id = uuid.uuid4()
    later = _chunk(repo_id, "pkg/same.py", "needle", 20, "needle")
    earlier = _chunk(repo_id, "pkg/same.py", "needle", 10, "needle")
    session = FakeSession([later, earlier])

    hits = await bm25.search_repo_bm25(
        session,  # type: ignore[arg-type]
        repo_id,
        "needle",
        index_revision=1,
        limit=5,
    )

    assert [row.start_line for row, _ in hits] == [10, 20]
    assert hits[0][1] == hits[1][1]


async def test_repo_bm25_cache_is_keyed_by_explicit_index_revision() -> None:
    repo_id = uuid.uuid4()
    first = _chunk(repo_id, "pkg/first.py", "first", 1, "first")
    second = _chunk(repo_id, "pkg/second.py", "second", 1, "second")
    session = FakeSession([first])

    first_hits = await bm25.search_repo_bm25(
        session,  # type: ignore[arg-type]
        repo_id,
        "first",
        index_revision=7,
        limit=5,
    )
    session.rows = [second]
    cached_hits = await bm25.search_repo_bm25(
        session,  # type: ignore[arg-type]
        repo_id,
        "first",
        index_revision=7,
        limit=5,
    )
    refreshed_hits = await bm25.search_repo_bm25(
        session,  # type: ignore[arg-type]
        repo_id,
        "second",
        index_revision=8,
        limit=5,
    )

    assert [row.id for row, _ in first_hits] == [first.id]
    assert [row.id for row, _ in cached_hits] == [first.id]
    assert [row.id for row, _ in refreshed_hits] == [second.id]
    assert len(session.statements) == 2
    assert list(bm25._corpus_cache) == [(repo_id, 8)]


async def test_repo_bm25_excludes_zero_score_documents_and_honors_limit() -> None:
    repo_id = uuid.uuid4()
    first = _chunk(repo_id, "pkg/a.py", "needle", 1, "needle needle")
    second = _chunk(repo_id, "pkg/b.py", "needle", 1, "needle")
    no_match = _chunk(repo_id, "pkg/c.py", "other", 1, "unrelated")
    session = FakeSession([no_match, second, first])

    hits = await bm25.search_repo_bm25(
        session,  # type: ignore[arg-type]
        repo_id,
        "needle",
        index_revision=1,
        limit=1,
    )

    assert len(hits) == 1
    assert hits[0][0].id == first.id


def _chunk(
    repo_id: uuid.UUID,
    file_path: str,
    symbol_name: str,
    start_line: int,
    content: str,
) -> ChunkRow:
    return ChunkRow(
        id=uuid.uuid4(),
        repo_id=repo_id,
        file_path=file_path,
        chunk_type="function",
        parent_symbol=None,
        symbol_name=symbol_name,
        signature=f"def {symbol_name}()",
        start_line=start_line,
        end_line=start_line + 1,
        imports=[],
        content=content,
        embedding=None,
    )
