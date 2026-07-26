"""Groundedness tests (DESIGN.md §2.3.4 / D-2.3.1)."""

from uuid import uuid4

from dcode_agent.groundedness import (
    CitationCheck,
    GroundednessResult,
    enforce_groundedness,
    extract_citations,
    verify,
)
from dcode_shared.db.models import Chunk, Symbol


class FakeSession:
    def __init__(self, *, chunks: list[Chunk], symbols: list[Symbol]) -> None:
        self.chunks = chunks
        self.symbols = symbols

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

    assert [(citation.file_path, citation.line, citation.verified) for citation in result.citations] == [
        ("src/flask/app.py", 42, True),
        ("src/flask/app.py", 999, False),
        ("src/flask/app.py", 42, True),
    ]
    assert result.score == 2 / 3


async def test_verify_marks_citations_unverified_without_db() -> None:
    repo_id = str(uuid4())

    result = await verify("See `src/flask/app.py:42` and `flask.app.Flask.run`.", repo_id, None)

    assert [citation.verified for citation in result.citations] == [False, False]
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
                symbol="src/flask/ghost.py", file_path="src/flask/ghost.py", line=999, verified=False
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
