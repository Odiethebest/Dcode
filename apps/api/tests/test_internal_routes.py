"""Internal retrieval API route contract tests."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from dcode_api.deps import get_db
from dcode_api.main import app
from dcode_api.routes import internal
from dcode_api.settings import api_settings
from dcode_shared.db.models import Chunk as ChunkRow
from dcode_shared.db.models import Repo, Symbol
from dcode_shared.internal import internal_auth_headers
from dcode_shared.schemas import Chunk, Location, ScoreComponents
from fastapi.testclient import TestClient


class FakeSession:
    def __init__(self, repo: Repo | None = None) -> None:
        self.repo = repo

    async def get(self, _: type[Repo], repo_id: uuid.UUID) -> Repo | None:
        if self.repo is not None and self.repo.id == repo_id:
            return self.repo
        return None


def override_db(session: FakeSession) -> None:
    async def dependency() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_db] = dependency


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _internal_headers() -> dict[str, str]:
    return internal_auth_headers(api_settings.internal_api_key)


def test_internal_search_route_returns_chunk_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    override_db(FakeSession(Repo(id=repo_id, url="https://example.com/repo.git", status="ready")))

    async def fake_search(
        _: FakeSession, passed_repo_id: uuid.UUID, query: str, k: int
    ) -> list[Chunk]:
        assert passed_repo_id == repo_id
        assert query == "auth"
        assert k == 3
        return [
            Chunk(
                chunk_id=uuid.uuid4(),
                file_path="src/requests/auth.py",
                symbol_name="HTTPBasicAuth",
                start_line=76,
                end_line=110,
                content="class HTTPBasicAuth(AuthBase): ...",
                score=42.0,
                score_components=ScoreComponents(dense=0.0, sparse=42.0, rerank=0.0),
            )
        ]

    monkeypatch.setattr(internal, "_search_chunks", fake_search)

    response = TestClient(app).get(
        f"/internal/search?repo_id={repo_id}&query=auth&k=3",
        headers=_internal_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["file_path"] == "src/requests/auth.py"
    assert body[0]["score_components"]["sparse"] == 42.0


def test_internal_graph_routes_return_location_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    override_db(FakeSession(Repo(id=repo_id, url="https://example.com/repo.git", status="ready")))
    location = Location(
        symbol="src.requests.auth.HTTPBasicAuth",
        file_path="src/requests/auth.py",
        line=76,
        chunk_id=uuid.uuid4(),
    )

    async def fake_find_definitions(
        _: FakeSession, passed_repo_id: uuid.UUID, symbol: str
    ) -> list[Location]:
        assert passed_repo_id == repo_id
        assert symbol == "HTTPBasicAuth"
        return [location]

    async def fake_find_references(
        _: FakeSession, passed_repo_id: uuid.UUID, symbol: str
    ) -> list[Location]:
        assert passed_repo_id == repo_id
        assert symbol == "HTTPBasicAuth"
        return [location]

    async def fake_get_dependencies(
        _: FakeSession, passed_repo_id: uuid.UUID, module: str
    ) -> list[Location]:
        assert passed_repo_id == repo_id
        assert module == "src.requests.api"
        return [location]

    async def fake_get_file_outline(
        _: FakeSession, passed_repo_id: uuid.UUID, path: str
    ) -> list[Location]:
        assert passed_repo_id == repo_id
        assert path == "src/requests/auth.py"
        return [location]

    monkeypatch.setattr(internal, "_find_definitions", fake_find_definitions)
    monkeypatch.setattr(internal, "_find_references", fake_find_references)
    monkeypatch.setattr(internal, "_get_dependencies", fake_get_dependencies)
    monkeypatch.setattr(internal, "_get_file_outline", fake_get_file_outline)
    client = TestClient(app)

    definition = client.get(
        f"/internal/find_definition?repo_id={repo_id}&symbol=HTTPBasicAuth",
        headers=_internal_headers(),
    )
    references = client.get(
        f"/internal/find_references?repo_id={repo_id}&symbol=HTTPBasicAuth",
        headers=_internal_headers(),
    )
    dependencies = client.get(
        f"/internal/get_dependencies?repo_id={repo_id}&module=src.requests.api",
        headers=_internal_headers(),
    )
    outline = client.get(
        f"/internal/get_file_outline?repo_id={repo_id}&path=src/requests/auth.py",
        headers=_internal_headers(),
    )

    assert definition.status_code == 200
    assert references.status_code == 200
    assert dependencies.status_code == 200
    assert outline.status_code == 200
    assert definition.json()[0]["symbol"] == "src.requests.auth.HTTPBasicAuth"
    assert outline.json()[0]["file_path"] == "src/requests/auth.py"


def test_internal_routes_404_for_unknown_repo() -> None:
    override_db(FakeSession())
    repo_id = uuid.uuid4()
    response = TestClient(app).get(
        f"/internal/search?repo_id={repo_id}&query=auth",
        headers=_internal_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REPO_NOT_FOUND"


def test_internal_routes_require_service_auth() -> None:
    repo_id = uuid.uuid4()
    response = TestClient(app).get(f"/internal/search?repo_id={repo_id}&query=auth")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_hybrid_search_fuses_sparse_and_dense_scores() -> None:
    row_sparse_and_dense = _chunk_row("auth.py", "HTTPBasicAuth", 85)
    row_sparse_only = _chunk_row("models.py", "PreparedRequest", 378)
    row_dense_only = _chunk_row("sessions.py", "SessionRedirectMixin", 109)

    sparse = [
        internal.SearchCandidate(row=row_sparse_and_dense, sparse_score=120.0),
        internal.SearchCandidate(row=row_sparse_only, sparse_score=40.0),
    ]
    dense = [
        internal.SearchCandidate(row=row_dense_only, dense_score=0.91),
        internal.SearchCandidate(row=row_sparse_and_dense, dense_score=0.42),
    ]

    fused = internal._identity_rerank(internal._fuse_search_candidates(sparse, dense))

    assert [candidate.row.id for candidate in fused] == [
        row_sparse_and_dense.id,
        row_dense_only.id,
        row_sparse_only.id,
    ]
    assert fused[0].sparse_score == 120.0
    assert fused[0].dense_score == 0.42
    assert fused[0].rerank_score == fused[0].fused_score
    assert fused[1].sparse_score == 0.0
    assert fused[1].dense_score == 0.91


async def test_search_chunks_degrades_to_sparse_only_when_embedding_is_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_id = uuid.uuid4()
    row = _chunk_row("src/requests/auth.py", "HTTPBasicAuth", 85, repo_id=repo_id)

    async def fake_sparse(
        _: object, passed_repo_id: uuid.UUID, query: str, terms: list[str], *, limit: int
    ) -> list[internal.SearchCandidate]:
        assert passed_repo_id == repo_id
        assert query == "HTTPBasicAuth"
        assert terms[0] == "httpbasicauth"
        assert limit >= 2
        return [internal.SearchCandidate(row=row, sparse_score=88.0)]

    async def fake_dense(
        _: object, passed_repo_id: uuid.UUID, query_vector: list[float] | None, *, limit: int
    ) -> list[internal.SearchCandidate]:
        assert passed_repo_id == repo_id
        assert query_vector is None
        assert limit >= 2
        return []

    monkeypatch.setattr(internal, "_search_sparse_candidates", fake_sparse)
    monkeypatch.setattr(internal, "_search_dense_candidates", fake_dense)

    chunks = await internal._search_chunks(object(), repo_id, "HTTPBasicAuth", 2)

    assert len(chunks) == 1
    assert chunks[0].symbol_name == "HTTPBasicAuth"
    assert chunks[0].score_components.sparse == 88.0
    assert chunks[0].score_components.dense == 0.0
    assert chunks[0].score == chunks[0].score_components.rerank


def test_select_symbol_matches_prefers_exact_qualified_name() -> None:
    exact = _symbol_row("src.requests.auth.HTTPBasicAuth", "class", "src/requests/auth.py", 85)
    suffix = _symbol_row("tests.helpers.HTTPBasicAuth", "class", "tests/helpers.py", 10)

    matches = internal._select_symbol_matches([suffix, exact], "src.requests.auth.HTTPBasicAuth")

    assert matches == [exact]


def test_select_symbol_matches_falls_back_to_suffix_match() -> None:
    first = _symbol_row("src.requests.auth.HTTPBasicAuth", "class", "src/requests/auth.py", 85)
    second = _symbol_row("tests.helpers.HTTPBasicAuth", "class", "tests/helpers.py", 10)

    matches = internal._select_symbol_matches([first, second], "HTTPBasicAuth")

    assert matches == [first, second]


def test_reference_edge_types_include_imports_for_modules_only() -> None:
    module_symbol = _symbol_row("src.requests.auth", "module", "src/requests/auth.py", 1)
    class_symbol = _symbol_row(
        "src.requests.auth.HTTPBasicAuth", "class", "src/requests/auth.py", 85
    )

    assert internal._reference_edge_types([module_symbol]) == ("calls", "references", "imports")
    assert internal._reference_edge_types([class_symbol]) == ("calls", "references")


def _chunk_row(
    file_path: str,
    symbol_name: str,
    start_line: int,
    *,
    repo_id: uuid.UUID | None = None,
) -> ChunkRow:
    return ChunkRow(
        id=uuid.uuid4(),
        repo_id=repo_id or uuid.uuid4(),
        file_path=file_path,
        chunk_type="class",
        parent_symbol=None,
        symbol_name=symbol_name,
        signature=f"class {symbol_name}",
        start_line=start_line,
        end_line=start_line + 10,
        imports=[],
        content=f"class {symbol_name}: ...",
        embedding=[0.0],
    )


def _symbol_row(qualified_name: str, kind: str, file_path: str, line: int) -> Symbol:
    return Symbol(
        id=uuid.uuid4(),
        repo_id=uuid.uuid4(),
        qualified_name=qualified_name,
        kind=kind,
        file_path=file_path,
        line=line,
        chunk_id=None,
    )
