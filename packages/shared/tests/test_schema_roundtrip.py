"""Schema roundtrip + cache key shape tests."""

from uuid import uuid4

import pytest

from dcode_shared.cache import (
    embedding_cache_key,
    job_state_key,
    query_cache_key,
    tool_cache_key,
)
from dcode_shared.events import (
    CitationEvent,
    FinalAnswerEvent,
    ThoughtEvent,
    sse_encode,
)
from dcode_shared.schemas import (
    QueryRequest,
    RepoCreateRequest,
    RepoCreateResponse,
    RepoStatus,
    RepoStatusResponse,
    StagesStatus,
    StageState,
)


def test_repo_create_request_validates() -> None:
    req = RepoCreateRequest(url="https://github.com/psf/requests.git")
    assert req.url.endswith(".git")


def test_repo_create_response_roundtrip() -> None:
    rid = uuid4()
    resp = RepoCreateResponse(repo_id=rid, status=RepoStatus.queued)
    parsed = RepoCreateResponse.model_validate_json(resp.model_dump_json())
    assert parsed.repo_id == rid
    assert parsed.status is RepoStatus.queued


def test_repo_status_shape_matches_tdd_5_1() -> None:
    status = RepoStatusResponse(
        repo_id=uuid4(),
        status=RepoStatus.embedding,
        progress=47,
        stages=StagesStatus(
            cloning=StageState.done,
            parsing=StageState.done,
            embedding=StageState.in_progress,
            graphing=StageState.pending,
        ),
        error=None,
    )
    payload = status.model_dump()
    assert set(payload["stages"]) == {"cloning", "parsing", "embedding", "graphing"}
    assert 0 <= payload["progress"] <= 100


def test_query_request_rejects_blank_query() -> None:
    with pytest.raises(ValueError):
        QueryRequest(repo_id=uuid4(), query="")


def test_cache_keys_match_design_3_3() -> None:
    assert embedding_cache_key("bge-code", "hello").startswith("embed:bge-code:")
    assert tool_cache_key("search_code", "rid", {"q": "x"}).startswith("tool:search_code:rid:")
    assert query_cache_key("rid", "q").startswith("query:rid:")
    assert job_state_key("rid") == "job:rid"


def test_sse_encode_wire_format() -> None:
    line = sse_encode("thought", ThoughtEvent(step=1, content="hi"))
    assert line.startswith(b"event: thought\n")
    assert b'"step":1' in line
    assert line.endswith(b"\n\n")


def test_final_answer_event_carries_citations() -> None:
    event = FinalAnswerEvent(
        answer="...",
        citations=[CitationEvent(symbol="X", file_path="a.py", line=1, verified=True)],
        groundedness=1.0,
    )
    parsed = FinalAnswerEvent.model_validate_json(event.model_dump_json())
    assert parsed.citations[0].verified is True
