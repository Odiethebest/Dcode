"""Groundedness regex extraction tests (DESIGN.md §2.3.4 / D-2.3.1)."""

from dcode_agent.groundedness import extract_citations


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
