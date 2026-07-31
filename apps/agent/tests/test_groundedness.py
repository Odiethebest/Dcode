"""Groundedness tests (DESIGN.md §2.3.4 / D-2.3.1)."""

from uuid import uuid4

from dcode_agent.groundedness import (
    CitationCheck,
    GroundednessResult,
    enforce_groundedness,
    extract_citations,
    extract_evidence_ids,
    verify,
)
from dcode_shared.db.models import Chunk, Symbol


class FakeScalars:
    """The slice of SQLAlchemy's Result that `_verify_symbol` uses."""

    def __init__(self, rows: list[Symbol]) -> None:
        self._rows = rows

    def scalars(self) -> "FakeScalars":
        return self

    def all(self) -> list[Symbol]:
        return list(self._rows)


class FakeSession:
    def __init__(self, *, chunks: list[Chunk], symbols: list[Symbol]) -> None:
        self.chunks = chunks
        self.symbols = symbols

    async def execute(self, stmt: object) -> FakeScalars:
        """Every symbol for the repo, with the name filter deliberately not applied.

        The real query narrows in SQL to a superset and lets
        `dcode_shared.symbols.select_symbol_matches` decide. Emulating the `LIKE`
        narrowing here would be a *third* copy of the matching rule, and a fake that
        got it subtly wrong would conceal the very disagreement that rule exists to
        remove. Returning the superset is what the real shape means.
        """
        params = stmt.compile().params  # type: ignore[attr-defined]
        repo_id = params["repo_id_1"]
        return FakeScalars([s for s in self.symbols if s.repo_id == repo_id])

    async def scalar(self, stmt: object) -> Chunk | Symbol | None:
        compiled = stmt.compile()
        sql = str(stmt)
        params = compiled.params
        if "FROM chunks" in sql:
            repo_id = params["repo_id_1"]
            file_path = params["file_path_1"]
            line = params["start_line_1"]
            for chunk in self.chunks:
                if (
                    chunk.repo_id == repo_id
                    and chunk.file_path == file_path
                    and chunk.start_line <= line <= chunk.end_line
                ):
                    return chunk
            return None
        if "FROM symbols" in sql:
            repo_id = params["repo_id_1"]
            qualified_name = params["qualified_name_1"]
            for symbol in self.symbols:
                if symbol.repo_id == repo_id and symbol.qualified_name == qualified_name:
                    return symbol
            return None
        raise AssertionError(f"unexpected statement: {sql}")


def test_extracts_file_line_references() -> None:
    answer = "See `src/flask/app.py:42` for the implementation, and also flask/cli.py:101."
    citations = extract_citations(answer)
    paths = {c[1] for c in citations}
    assert "src/flask/app.py" in paths
    assert "flask/cli.py" in paths


def test_extracts_qualified_symbol_references() -> None:
    answer = "The `flask.app.Flask.run` method binds to the server."
    citations = extract_citations(answer)
    symbols = {c[0] for c in citations}
    assert "flask.app.Flask.run" in symbols


def test_returns_empty_when_no_references_present() -> None:
    assert extract_citations("This answer has no code references.") == []


def test_extracts_server_owned_evidence_ids_in_occurrence_order() -> None:
    assert extract_evidence_ids("First [C2], then [C1], then [C2].") == ["C2", "C1", "C2"]


async def test_verify_checks_file_ranges_and_symbols_against_db_fixture() -> None:
    repo_id = uuid4()
    db = FakeSession(
        chunks=[
            Chunk(
                id=uuid4(),
                repo_id=repo_id,
                file_path="src/flask/app.py",
                chunk_type="class",
                parent_symbol=None,
                symbol_name="Flask",
                signature="class Flask",
                start_line=40,
                end_line=80,
                imports=[],
                content="class Flask: ...",
                embedding=[0.0],
            )
        ],
        symbols=[
            Symbol(
                id=uuid4(),
                repo_id=repo_id,
                qualified_name="flask.app.Flask.run",
                kind="method",
                file_path="src/flask/app.py",
                line=42,
                chunk_id=None,
            )
        ],
    )

    result = await verify(
        "See `src/flask/app.py:42` and `flask.app.Flask.run`, but not `src/flask/app.py:999`.",
        str(repo_id),
        db,
    )

    assert [
        (citation.file_path, citation.line, citation.verified) for citation in result.citations
    ] == [
        ("src/flask/app.py", 42, True),
        ("src/flask/app.py", 999, False),
        ("src/flask/app.py", 42, True),
    ]
    assert result.score == 2 / 3


async def test_verify_accepts_a_symbol_written_without_the_indexed_prefix() -> None:
    """The guardrail resolves a symbol the way the find-definition tool does.

    `symbols.qualified_name` is built from the repository's directory layout, so the
    indexed name carries a `src.` component that nobody writes. While this function
    matched exactly, the tool answered "here it is" for `api.get` and the guardrail
    answered "that does not exist, strip it" — about one string, over one table,
    inside one request.

    **This test is why `_verify_symbol` is mutation-covered at all.** The identity
    assertion in `test_citable_tokens.py` proves the shared rule is *imported*; only
    an end-to-end verify like this one proves it is *used*. Reverting the function to
    `qualified_name == symbol` leaves that identity check green and turns this red —
    which a mutation run established, after the first pass reported four of five
    mutations killed and this one surviving.
    """
    repo_id = uuid4()
    db = FakeSession(
        chunks=[],
        symbols=[
            Symbol(
                id=uuid4(),
                repo_id=repo_id,
                qualified_name="src.requests.api.get",
                kind="function",
                file_path="src/requests/api.py",
                line=62,
                chunk_id=None,
            )
        ],
    )

    result = await verify(
        "The entry point is `requests.api.get`, reached via `api.get`.", str(repo_id), db
    )

    assert [(c.symbol, c.file_path, c.line, c.verified) for c in result.citations] == [
        ("requests.api.get", "src/requests/api.py", 62, True),
        ("api.get", "src/requests/api.py", 62, True),
    ]
    assert result.score == 1.0, (
        "both names refer to the one indexed symbol; rejecting them is the "
        "disagreement dcode_shared.symbols exists to remove"
    )


async def test_verify_still_rejects_a_symbol_that_is_not_indexed() -> None:
    """Loosening the rule must not make it accept anything with a matching tail.

    The pair to the test above: `select_symbol_matches` requires the match to fall on
    a component boundary, so a name that merely ends in the same letters is still
    unverified and still redacted.
    """
    repo_id = uuid4()
    db = FakeSession(
        chunks=[],
        symbols=[
            Symbol(
                id=uuid4(),
                repo_id=repo_id,
                qualified_name="src.requests.api.get",
                kind="function",
                file_path="src/requests/api.py",
                line=62,
                chunk_id=None,
            )
        ],
    )

    result = await verify("Handled by `legacy_api.get` and `requests.api.fetch`.", str(repo_id), db)

    assert [(c.symbol, c.verified) for c in result.citations] == [
        ("legacy_api.get", False),
        ("requests.api.fetch", False),
    ]
    assert result.score == 0.0


async def test_verify_marks_citations_unverified_without_db() -> None:
    repo_id = str(uuid4())

    result = await verify("See `src/flask/app.py:42` and `flask.app.Flask.run`.", repo_id, None)

    assert [citation.verified for citation in result.citations] == [False, False]
    assert result.score == 0.0


async def test_evidence_id_mode_ignores_ordinary_dotted_inline_code() -> None:
    repo_id = uuid4()
    db = FakeSession(
        chunks=[
            Chunk(
                id=uuid4(),
                repo_id=repo_id,
                file_path="src/retrieval/hybrid_search.py",
                chunk_type="method",
                parent_symbol="HybridRetriever",
                symbol_name="retrieve",
                signature="def retrieve(self, query):",
                start_line=60,
                end_line=90,
                imports=[],
                content="def retrieve(self, query): ...",
                embedding=[0.0],
            )
        ],
        symbols=[],
    )

    answer = (
        "It calls `self.faiss.retrieve` and `self.bm25.retrieve`; "
        "the implementation is shown by [C1]."
    )
    result = await verify(
        answer,
        str(repo_id),
        db,
        evidence_catalog={"C1": "src/retrieval/hybrid_search.py:63"},
    )

    assert [
        (check.source_token, check.display_token, check.verified) for check in result.citations
    ] == [("[C1]", "src/retrieval/hybrid_search.py:63", True)]
    assert result.score == 1.0

    enforced = enforce_groundedness(answer, result, threshold=0.95)
    assert "`self.faiss.retrieve`" in enforced.answer
    assert "`self.bm25.retrieve`" in enforced.answer
    assert "[C1]" not in enforced.answer
    assert "`src/retrieval/hybrid_search.py:63`" in enforced.answer


async def test_evidence_id_mode_redacts_unknown_ids() -> None:
    result = await verify(
        "This claim cites an invented ID [C999].",
        str(uuid4()),
        None,
        evidence_catalog={"C1": "src/retrieval/hybrid_search.py:63"},
    )

    assert [(check.source_token, check.verified) for check in result.citations] == [
        ("[C999]", False)
    ]
    enforced = enforce_groundedness(
        "This claim cites an invented ID [C999].", result, threshold=0.95
    )
    assert "[C999]" not in enforced.answer
    assert "[unverified reference removed]" in enforced.answer


def test_adjacent_evidence_ids_render_as_separate_citations() -> None:
    answer = "Both claims are supported [C1][C2]."
    result = GroundednessResult(
        citations=[
            CitationCheck(
                symbol="a.py",
                file_path="a.py",
                line=1,
                verified=True,
                source_token="[C1]",
                display_token="a.py:1",
            ),
            CitationCheck(
                symbol="b.py",
                file_path="b.py",
                line=2,
                verified=True,
                source_token="[C2]",
                display_token="b.py:2",
            ),
        ],
        score=1.0,
    )

    enforced = enforce_groundedness(answer, result, threshold=0.95)

    assert enforced.answer == "Both claims are supported `a.py:1` `b.py:2`."


async def test_evidence_id_mode_still_checks_explicit_file_line_references() -> None:
    result = await verify(
        "Ordinary `self.faiss.retrieve`, invented location `ghost.py:999`.",
        str(uuid4()),
        None,
        evidence_catalog={},
    )

    assert [(check.symbol, check.verified) for check in result.citations] == [("ghost.py", False)]
    assert result.score == 0.0


def test_enforce_redacts_unverified_file_reference_and_keeps_verified() -> None:
    answer = (
        "Definition matches:\n"
        "- `Flask` in `src/flask/app.py:42`\n"
        "- `ghost` in `src/flask/ghost.py:999`"
    )
    result = GroundednessResult(
        citations=[
            CitationCheck(
                symbol="src/flask/app.py", file_path="src/flask/app.py", line=42, verified=True
            ),
            CitationCheck(
                symbol="src/flask/ghost.py",
                file_path="src/flask/ghost.py",
                line=999,
                verified=False,
            ),
        ],
        score=0.5,
    )

    enforced = enforce_groundedness(answer, result, threshold=0.95)

    assert "`src/flask/app.py:42`" in enforced.answer  # verified reference kept
    assert "src/flask/ghost.py:999" not in enforced.answer  # unverified reference redacted
    assert "[unverified reference removed]" in enforced.answer
    assert [check.file_path for check in enforced.citations] == ["src/flask/app.py"]
    assert enforced.redacted_count == 1
    assert enforced.score == 0.5
    assert "below the 0.95 guardrail" in enforced.answer  # score < threshold → warning footer


def test_enforce_redacts_unverified_symbol_reference() -> None:
    answer = "The `flask.app.Flask.ghost` helper handles it."
    result = GroundednessResult(
        citations=[
            CitationCheck(symbol="flask.app.Flask.ghost", file_path="", line=0, verified=False)
        ],
        score=0.0,
    )

    enforced = enforce_groundedness(answer, result, threshold=0.95)

    assert "flask.app.Flask.ghost" not in enforced.answer
    assert "[unverified reference removed]" in enforced.answer
    assert enforced.citations == []


def test_symbol_redaction_does_not_corrupt_a_longer_verified_file_path() -> None:
    answer = (
        "The helper module is `hybrid_search.py`; its implementation is at "
        "`src/retrieval/hybrid_search.py:63`."
    )
    result = GroundednessResult(
        citations=[
            CitationCheck(
                symbol="src/retrieval/hybrid_search.py",
                file_path="src/retrieval/hybrid_search.py",
                line=63,
                verified=True,
            ),
            CitationCheck(symbol="hybrid_search.py", file_path="", line=0, verified=False),
        ],
        score=0.5,
    )

    enforced = enforce_groundedness(answer, result, threshold=0.95)

    assert "`src/retrieval/hybrid_search.py:63`" in enforced.answer
    assert "`hybrid_search.py`" not in enforced.answer
    assert enforced.answer.count("[unverified reference removed]") == 1


def test_enforce_localizes_redaction_and_guardrail_note_for_chinese() -> None:
    answer = "不存在的调用位于 `src/retrieval/ghost.py:999`。"
    result = GroundednessResult(
        citations=[
            CitationCheck(
                symbol="src/retrieval/ghost.py",
                file_path="src/retrieval/ghost.py",
                line=999,
                verified=False,
            )
        ],
        score=0.0,
    )

    enforced = enforce_groundedness(answer, result, threshold=0.95, chinese=True)

    assert "[已移除未验证引用]" in enforced.answer
    assert "引用可信度 0.00 低于 0.95" in enforced.answer
    assert "unverified reference" not in enforced.answer


def test_enforce_leaves_fully_grounded_answer_untouched() -> None:
    answer = "See `src/flask/app.py:42`."
    result = GroundednessResult(
        citations=[
            CitationCheck(
                symbol="src/flask/app.py", file_path="src/flask/app.py", line=42, verified=True
            )
        ],
        score=1.0,
    )

    enforced = enforce_groundedness(answer, result, threshold=0.95)

    assert enforced.answer == answer  # nothing redacted, no footer
    assert enforced.redacted_count == 0
    assert [check.verified for check in enforced.citations] == [True]


def test_enforce_redacts_inline_without_footer_when_score_meets_threshold() -> None:
    answer = "- `a.py:1` and `b.py:2`"
    result = GroundednessResult(
        citations=[
            CitationCheck(symbol="a.py", file_path="a.py", line=1, verified=True),
            CitationCheck(symbol="b.py", file_path="b.py", line=2, verified=False),
        ],
        score=0.5,
    )

    enforced = enforce_groundedness(answer, result, threshold=0.5)

    assert "`a.py:1`" in enforced.answer
    assert "b.py:2" not in enforced.answer  # still redacted (hard guardrail)
    assert "guardrail" not in enforced.answer  # score == threshold → no warning footer
    assert enforced.redacted_count == 1
