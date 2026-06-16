"""Internal retrieval API route contract tests."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from dcode_api.deps import get_db
from dcode_api.main import app
from dcode_api.routes import internal
from dcode_shared.db.models import Repo
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

    response = TestClient(app).get(f"/internal/search?repo_id={repo_id}&query=auth&k=3")

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

    definition = client.get(f"/internal/find_definition?repo_id={repo_id}&symbol=HTTPBasicAuth")
    references = client.get(f"/internal/find_references?repo_id={repo_id}&symbol=HTTPBasicAuth")
    dependencies = client.get(
        f"/internal/get_dependencies?repo_id={repo_id}&module=src.requests.api"
    )
    outline = client.get(f"/internal/get_file_outline?repo_id={repo_id}&path=src/requests/auth.py")

    assert definition.status_code == 200
    assert references.status_code == 200
    assert dependencies.status_code == 200
    assert outline.status_code == 200
    assert definition.json()[0]["symbol"] == "src.requests.auth.HTTPBasicAuth"
    assert outline.json()[0]["file_path"] == "src/requests/auth.py"


def test_internal_routes_404_for_unknown_repo() -> None:
    override_db(FakeSession())
    repo_id = uuid.uuid4()
    response = TestClient(app).get(f"/internal/search?repo_id={repo_id}&query=auth")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REPO_NOT_FOUND"
