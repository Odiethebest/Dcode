"""Execution tests for agent tools."""

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from dcode_agent.settings import agent_settings
from dcode_agent.tools import common
from dcode_agent.tools.find_definition import FindDefinitionArgs, FindDefinitionTool
from dcode_agent.tools.find_references import FindReferencesArgs, FindReferencesTool
from dcode_agent.tools.get_dependencies import GetDependenciesArgs, GetDependenciesTool
from dcode_agent.tools.get_file_outline import GetFileOutlineArgs, GetFileOutlineTool
from dcode_agent.tools.grep import GrepArgs, GrepTool
from dcode_agent.tools.list_directory import ListDirectoryArgs, ListDirectoryTool
from dcode_agent.tools.read_file import ReadFileArgs, ReadFileTool
from dcode_agent.tools.search_code import SearchCodeArgs, SearchCodeTool


@pytest.fixture
def repo_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    repo_id = str(uuid4())
    repo_root = tmp_path / repo_id
    repo_root.mkdir(parents=True)
    monkeypatch.setattr(agent_settings, "workdir_base", str(tmp_path))
    return repo_id, repo_root


async def test_search_code_calls_internal_search(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = str(uuid4())

    async def fake_fetch(endpoint: str, passed_repo_id: str, params: dict[str, object]) -> list[dict[str, object]]:
        assert endpoint == "search"
        assert passed_repo_id == repo_id
        assert params == {"query": "auth", "k": 3}
        return [
            {
                "chunk_id": str(uuid4()),
                "file_path": "src/requests/auth.py",
                "symbol_name": "HTTPBasicAuth",
                "start_line": 85,
                "end_line": 113,
                "content": "class HTTPBasicAuth(AuthBase): ...",
                "score": 1.0,
                "score_components": {"dense": 0.0, "sparse": 1.0, "rerank": 1.0},
            }
        ]

    monkeypatch.setattr(common, "fetch_internal_json", fake_fetch)

    result = await SearchCodeTool().execute(repo_id, SearchCodeArgs(query="auth", k=3))

    assert result.chunks[0].file_path == "src/requests/auth.py"
    assert result.chunks[0].symbol_name == "HTTPBasicAuth"


@pytest.mark.parametrize(
    ("tool", "args", "endpoint", "field_name"),
    [
        (FindDefinitionTool(), FindDefinitionArgs(symbol="HTTPBasicAuth"), "find_definition", "locations"),
        (FindReferencesTool(), FindReferencesArgs(symbol="src.requests.auth"), "find_references", "locations"),
        (
            GetDependenciesTool(),
            GetDependenciesArgs(module="src.requests.api"),
            "get_dependencies",
            "locations",
        ),
        (
            GetFileOutlineTool(),
            GetFileOutlineArgs(path="src/requests/auth.py"),
            "get_file_outline",
            "locations",
        ),
    ],
)
async def test_graph_tools_call_internal_api(
    monkeypatch: pytest.MonkeyPatch,
    tool: Any,
    args: Any,
    endpoint: str,
    field_name: str,
) -> None:
    repo_id = str(uuid4())

    async def fake_fetch(
        passed_endpoint: str,
        passed_repo_id: str,
        params: dict[str, object],
    ) -> list[dict[str, object]]:
        assert passed_endpoint == endpoint
        assert passed_repo_id == repo_id
        assert params
        return [
            {
                "symbol": "src.requests.auth.HTTPBasicAuth",
                "file_path": "src/requests/auth.py",
                "line": 85,
                "chunk_id": None,
            }
        ]

    monkeypatch.setattr(common, "fetch_internal_json", fake_fetch)

    result = await tool.execute(repo_id, args)

    assert getattr(result, field_name)[0].file_path == "src/requests/auth.py"


async def test_get_file_outline_normalizes_repo_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_id = str(uuid4())

    async def fake_fetch(
        passed_endpoint: str,
        passed_repo_id: str,
        params: dict[str, object],
    ) -> list[dict[str, object]]:
        assert passed_endpoint == "get_file_outline"
        assert passed_repo_id == repo_id
        assert params == {"path": "src/requests/auth.py"}
        return [
            {
                "symbol": "src.requests.auth.HTTPBasicAuth",
                "file_path": "src/requests/auth.py",
                "line": 85,
                "chunk_id": None,
            }
        ]

    monkeypatch.setattr(common, "fetch_internal_json", fake_fetch)

    result = await GetFileOutlineTool().execute(
        repo_id,
        GetFileOutlineArgs(path="./src//requests/auth.py"),
    )

    assert result.path == "src/requests/auth.py"
    assert result.locations[0].file_path == "src/requests/auth.py"


async def test_get_file_outline_rejects_path_traversal() -> None:
    repo_id = str(uuid4())

    with pytest.raises(ValueError, match="path escapes repo workdir"):
        await GetFileOutlineTool().execute(repo_id, GetFileOutlineArgs(path="../secret.py"))


async def test_read_file_reads_inclusive_line_range(repo_workspace: tuple[str, Path]) -> None:
    repo_id, repo_root = repo_workspace
    file_path = repo_root / "pkg" / "mod.py"
    file_path.parent.mkdir()
    file_path.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    result = await ReadFileTool().execute(repo_id, ReadFileArgs(path="pkg/mod.py", line_range=(2, 3)))

    assert result.path == "pkg/mod.py"
    assert result.content == "line2\nline3"


async def test_read_file_rejects_path_traversal(repo_workspace: tuple[str, Path]) -> None:
    repo_id, _ = repo_workspace

    with pytest.raises(ValueError, match="path escapes repo workdir"):
        await ReadFileTool().execute(repo_id, ReadFileArgs(path="../secret.txt", line_range=(1, 1)))


async def test_list_directory_returns_sorted_visible_entries(
    repo_workspace: tuple[str, Path],
) -> None:
    repo_id, repo_root = repo_workspace
    (repo_root / "b.py").write_text("print('b')\n", encoding="utf-8")
    (repo_root / "a_dir").mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "__pycache__").mkdir()

    result = await ListDirectoryTool().execute(repo_id, ListDirectoryArgs(path="."))

    assert [(entry.name, entry.kind) for entry in result.entries] == [
        ("a_dir", "dir"),
        ("b.py", "file"),
    ]


async def test_list_directory_rejects_path_traversal(repo_workspace: tuple[str, Path]) -> None:
    repo_id, _ = repo_workspace

    with pytest.raises(ValueError, match="path escapes repo workdir"):
        await ListDirectoryTool().execute(repo_id, ListDirectoryArgs(path="../"))


async def test_grep_falls_back_to_python_when_ripgrep_unavailable(
    repo_workspace: tuple[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_id, repo_root = repo_workspace
    (repo_root / "pkg").mkdir()
    (repo_root / "pkg" / "mod.py").write_text(
        "needle = 1\nother = 2\nif needle:\n    pass\n",
        encoding="utf-8",
    )
    (repo_root / ".venv").mkdir()
    (repo_root / ".venv" / "ignore.py").write_text("needle = 3\n", encoding="utf-8")
    monkeypatch.setattr("dcode_agent.tools.grep.shutil.which", lambda _: None)

    result = await GrepTool().execute(repo_id, GrepArgs(pattern="needle"))

    assert [(location.file_path, location.line) for location in result.locations] == [
        ("pkg/mod.py", 1),
        ("pkg/mod.py", 3),
    ]
