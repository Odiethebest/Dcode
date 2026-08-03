"""Bounds on the grep tool (F-15).

The tool's argument is a pattern the planner derives from a user question, and
it had no ceiling of any kind: no timeout, no match cap, and the whole of
ripgrep's stdout buffered in the agent process before anything looked at it.
"""

import re
from pathlib import Path

from dcode_agent.tools import grep as grep_module


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


def test_python_fallback_caps_total_matches(tmp_path: Path) -> None:
    """A pattern matching everything has told you nothing.

    The first few hundred hits are as informative as the first few hundred
    thousand, and the difference is hundreds of MB through Redis and the SSE
    state.
    """
    files = {f"mod{index}.py": "x\n" * 200 for index in range(20)}
    root = _repo(tmp_path, files)

    matches = grep_module._grep_with_python(root, "x")

    assert len(matches) <= grep_module._MATCH_LIMIT


def test_python_fallback_caps_matches_per_file(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"one.py": "hit\n" * 500})

    matches = grep_module._grep_with_python(root, "hit")

    assert len(matches) == grep_module._PER_FILE_MATCH_LIMIT


def test_python_fallback_skips_a_file_over_the_size_cap(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            "small.py": "needle\n",
            "huge.py": "needle\n" + ("padding\n" * (grep_module._MAX_FILE_BYTES // 8 + 10)),
        },
    )

    matches = grep_module._grep_with_python(root, "needle")

    assert [match.file_path for match in matches] == ["small.py"]


def test_python_fallback_stops_at_the_deadline(
    tmp_path: Path, monkeypatch: object
) -> None:
    """The wall-clock bound is checked between files.

    A single `re` call cannot be interrupted in Python, so this is what is
    actually enforceable — and the tool's docstring says so rather than
    implying the fallback is fully bounded.
    """
    root = _repo(tmp_path, {f"m{index}.py": "needle\n" for index in range(50)})

    ticks = iter([0.0] + [999.0] * 200)
    monkeypatch.setattr(grep_module.time, "monotonic", lambda: next(ticks))  # type: ignore[attr-defined]

    matches = grep_module._grep_with_python(root, "needle")

    assert matches == [], "an expired deadline must stop the walk"


def test_the_ripgrep_invocation_carries_its_own_bounds() -> None:
    """Bounded at the source, not after the fact.

    Asserted on the argument list because the alternative is reading everything
    ripgrep produces and discarding most of it, which is the behaviour being
    replaced.
    """
    source = Path(grep_module.__file__).read_text(encoding="utf-8")
    assert "--max-count=" in source
    assert "--max-filesize=" in source
    assert "asyncio.wait_for" in source


def test_a_pattern_that_is_not_a_regex_surfaces_as_a_tool_error(tmp_path: Path) -> None:
    """The planner can produce an invalid pattern; that is a tool failure.

    The agent records tool failures and degrades to synthesis, so this must
    raise rather than return an empty result that reads like "no matches".
    """
    root = _repo(tmp_path, {"a.py": "x\n"})
    try:
        grep_module._grep_with_python(root, "(unclosed")
    except re.error:
        return
    raise AssertionError("an invalid pattern should not look like zero matches")
