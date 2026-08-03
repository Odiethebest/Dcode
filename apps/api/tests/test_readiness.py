"""/readyz (F-10).

/healthz answers `ok` with every dependency down — correct for liveness,
useless for deciding whether this process can serve. These cover the deep probe
and, in particular, the embedding-dimension check that Deploy.md §5.4 asks for,
because a dimension mismatch is the one misconfiguration in this stack that
produces no error at all.
"""

import pytest
from dcode_api import readiness
from dcode_api.main import app
from fastapi.testclient import TestClient


def _readyz(monkeypatch: pytest.MonkeyPatch, checks: list[readiness.Check]) -> tuple[int, dict]:
    async def stub() -> list[readiness.Check]:
        return checks

    monkeypatch.setattr(readiness, "run_checks", stub)
    response = TestClient(app).get("/readyz")
    return response.status_code, response.json()


def test_ready_when_every_check_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    code, body = _readyz(
        monkeypatch,
        [readiness.Check("database", True), readiness.Check("redis", True)],
    )
    assert code == 200
    assert body["status"] == "ready"


def test_not_ready_is_a_503_with_a_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """503, not 200-with-a-body.

    A load balancer reads the status line. Reporting a failure only in the JSON
    would keep sending traffic to a process that cannot serve it.
    """
    code, body = _readyz(
        monkeypatch,
        [
            readiness.Check("database", False, "OperationalError: connection refused"),
            readiness.Check("redis", True),
        ],
    )
    assert code == 503
    assert body["status"] == "not ready"
    failed = [check for check in body["checks"] if not check["ok"]]
    assert len(failed) == 1
    assert "connection refused" in failed[0]["detail"]


def test_healthz_stays_shallow_and_open() -> None:
    """Unchanged on purpose.

    A liveness probe that fails when a dependency is down gets the process
    restarted, which fixes nothing and loses the logs.
    """
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_a_dimension_mismatch_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """The failure mode §5.4 describes, which nothing else catches.

    `chunks.embedding` is fixed at migration time. A service configured for
    another dimension either fails every insert or searches real vectors with a
    stub all-zero query vector and returns noise — with no error either way.
    """
    from dcode_api.settings import api_settings

    monkeypatch.setattr(api_settings, "embedding_dim", 768)
    monkeypatch.setattr(readiness, "SessionLocal", _session_returning(1024))

    check = await readiness._check_embedding_dim()

    assert check.ok is False
    assert check.detail is not None
    assert "768" in check.detail and "1024" in check.detail
    assert "restarting" in check.detail, "the reason should say a restart will not fix it"


async def test_a_matching_dimension_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from dcode_api.settings import api_settings

    monkeypatch.setattr(api_settings, "embedding_dim", 768)
    monkeypatch.setattr(readiness, "SessionLocal", _session_returning(768))

    assert (await readiness._check_embedding_dim()).ok is True


async def test_a_missing_chunks_table_is_skipped_not_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the first migration there is nothing to disagree with.

    Reporting not-ready would block a deployment that has not reached the
    migration step yet, which is a real ordering in the Railway runbook.
    """
    monkeypatch.setattr(readiness, "SessionLocal", _session_raising())

    check = await readiness._check_embedding_dim()

    assert check.ok is True
    assert check.detail is not None and "not checked" in check.detail


def _session_returning(dimension: int | None) -> object:
    class _Result:
        def scalar_one_or_none(self) -> int | None:
            return dimension

    class _Session:
        async def __aenter__(self) -> "_Session":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def execute(self, _statement: object) -> _Result:
            return _Result()

    return _Session


def _session_raising() -> object:
    class _Session:
        async def __aenter__(self) -> "_Session":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def execute(self, _statement: object) -> object:
            raise RuntimeError('relation "chunks" does not exist')

    return _Session
