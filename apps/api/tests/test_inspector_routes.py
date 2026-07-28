"""Inspector (source + call-graph) route contract tests."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from dcode_api.deps import get_db
from dcode_api.main import app
from dcode_api.routes import inspector
from dcode_shared.db.models import Repo
from dcode_shared.schemas import Location, SourceResponse, SymbolNeighbors
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


def _ready_repo(repo_id: uuid.UUID) -> Repo:
    return Repo(id=repo_id, url="https://example.com/repo.git", status="ready")


def test_source_route_returns_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    override_db(FakeSession(_ready_repo(repo_id)))

    async def fake_resolve(
        _db: object,
        passed_repo_id: uuid.UUID,
        file_path: str | None,
        line: int | None,
        symbol: str | None,
    ) -> SourceResponse:
        assert passed_repo_id == repo_id
        assert file_path == "src/requests/auth.py"
        assert line == 85
        return SourceResponse(
            found=True,
            granularity="chunk",
            file_path=file_path,
            symbol_name="HTTPBasicAuth.__call__",
            chunk_type="method",
            start_line=83,
            end_line=89,
            cited_line=85,
            content="def __call__(self, r): ...",
        )

    monkeypatch.setattr(inspector, "_resolve_source", fake_resolve)

    response = TestClient(app).get(
        f"/api/v1/repos/{repo_id}/source?file_path=src/requests/auth.py&line=85"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["granularity"] == "chunk"
    assert body["content"].startswith("def __call__")


def test_source_route_returns_200_for_unresolved_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 'never 500' promise at the route: an unresolvable citation is a 200
    honest empty state, not a server error."""
    repo_id = uuid.uuid4()
    override_db(FakeSession(_ready_repo(repo_id)))

    async def fake_resolve(
        _db: object,
        passed_repo_id: uuid.UUID,
        file_path: str | None,
        line: int | None,
        symbol: str | None,
    ) -> SourceResponse:
        return SourceResponse(found=False, granularity="none", file_path=file_path, cited_line=line)

    monkeypatch.setattr(inspector, "_resolve_source", fake_resolve)

    response = TestClient(app).get(
        f"/api/v1/repos/{repo_id}/source?file_path=x.py&line=999&symbol=Nope"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert body["granularity"] == "none"


async def test_resolve_source_degrades_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolver-level 'never 500': when every lookup misses, the source resolves
    to found=false / granularity=none instead of raising."""
    repo_id = uuid.uuid4()

    async def none_chunk(*_args: object, **_kwargs: object) -> None:
        return None

    async def none_symbol(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(inspector, "_chunk_containing", none_chunk)
    monkeypatch.setattr(inspector, "_resolve_symbol", none_symbol)

    result = await inspector._resolve_source(object(), repo_id, "x.py", 999, "Nope")  # type: ignore[arg-type]

    assert result.found is False
    assert result.granularity == "none"
    assert result.cited_line == 999


def test_source_route_404_for_unknown_repo() -> None:
    override_db(FakeSession())
    repo_id = uuid.uuid4()

    response = TestClient(app).get(f"/api/v1/repos/{repo_id}/source?symbol=Foo")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REPO_NOT_FOUND"


def test_neighbors_route_groups_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    override_db(FakeSession(_ready_repo(repo_id)))
    caller = Location(
        symbol="requests.models.PreparedRequest.prepare_auth",
        file_path="src/requests/models.py",
        line=471,
        chunk_id=uuid.uuid4(),
    )
    callee = Location(
        symbol="requests.auth._basic_auth_str",
        file_path="src/requests/auth.py",
        line=34,
        chunk_id=None,
    )

    async def fake_neighbors(
        _db: object, passed_repo_id: uuid.UUID, symbol: str
    ) -> SymbolNeighbors:
        assert passed_repo_id == repo_id
        assert symbol == "HTTPBasicAuth.__call__"
        return SymbolNeighbors(
            found=True,
            symbol=symbol,
            file_path="src/requests/auth.py",
            line=85,
            called_by=[caller],
            calls=[callee],
            references=[],
        )

    monkeypatch.setattr(inspector, "_resolve_neighbors", fake_neighbors)

    response = TestClient(app).get(
        f"/api/v1/repos/{repo_id}/neighbors?symbol=HTTPBasicAuth.__call__"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["called_by"][0]["file_path"] == "src/requests/models.py"
    assert body["calls"][0]["symbol"].endswith("_basic_auth_str")


async def test_resolve_neighbors_unknown_symbol_returns_found_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_id = uuid.uuid4()

    async def none_symbol(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(inspector, "_resolve_symbol", none_symbol)

    result = await inspector._resolve_neighbors(object(), repo_id, "Ghost")  # type: ignore[arg-type]

    assert result.found is False
    assert result.symbol == "Ghost"
    assert result.called_by == []
