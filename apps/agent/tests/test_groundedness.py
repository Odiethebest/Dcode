"""Groundedness tests (DESIGN.md §2.3.4 / D-2.3.1)."""

from uuid import uuid4

from dcode_agent.groundedness import extract_citations, verify
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
