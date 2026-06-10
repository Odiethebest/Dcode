"""API gateway smoke tests: health + skeleton schema contracts."""

import uuid

from fastapi.testclient import TestClient

from dcode_api.main import app


def test_healthz_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_submit_repo_returns_202_with_correct_shape() -> None:
    """DESIGN.md §4.1 POST /api/v1/repos must return 202 + RepoCreateResponse."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/repos",
        json={"url": "https://github.com/psf/requests.git"},
    )
    assert response.status_code == 202
    body = response.json()
    assert "repo_id" in body
    assert body["status"] == "queued"


def test_repo_status_returns_correct_shape() -> None:
    """DESIGN.md §4.1 GET /api/v1/repos/{id}/status must return RepoStatusResponse."""
    client = TestClient(app)
    rid = str(uuid.uuid4())
    response = client.get(f"/api/v1/repos/{rid}/status")
    assert response.status_code == 200
    body = response.json()
    assert body["repo_id"] == rid
    assert set(body["stages"]) == {"cloning", "parsing", "embedding", "graphing"}
    assert 0 <= body["progress"] <= 100
