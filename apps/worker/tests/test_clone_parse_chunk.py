"""Clone, parse, and AST chunk stage tests."""

import subprocess
from pathlib import Path
from uuid import uuid4

from dcode_shared.schemas import ChunkType
from dcode_worker.context import PipelineContext
from dcode_worker.stages import chunk, clone, parse


async def test_clone_stage_clones_into_repo_scoped_workdir(tmp_path: Path, monkeypatch) -> None:
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    (source_repo / "pkg").mkdir()
    (source_repo / "pkg" / "mod.py").write_text("def ok():\n    return True\n", encoding="utf-8")
    _git(source_repo, "init")
    _git(source_repo, "add", ".")
    _git(source_repo, "commit", "-m", "initial")
    expected_sha = _git(source_repo, "rev-parse", "HEAD").strip()

    workdir_base = tmp_path / "workdirs"
    monkeypatch.setattr(clone.worker_settings, "workdir_base", str(workdir_base))
    repo_id = str(uuid4())
    ctx = PipelineContext(repo_id=repo_id, repo_url=source_repo.as_uri())

    result = await clone.run(ctx)

    assert result.workdir == str(workdir_base / repo_id)
    assert result.commit_sha == expected_sha
    assert Path(result.workdir, "pkg", "mod.py").read_text(encoding="utf-8").startswith("def ok")


async def test_parse_and_chunk_python_ast_boundaries(tmp_path: Path) -> None:
    workdir = tmp_path / "repo"
    package = workdir / "pkg"
    package.mkdir(parents=True)
    (package / "example.py").write_text(
        '''"""Module docs."""
import os
from collections import defaultdict as dd


def top(a: int) -> str:
    import json
    return str(a)


class Greeter:
    """Greeter docs."""

    def hello(self, name: str) -> str:
        return name

    async def goodbye(self) -> None:
        return None
''',
        encoding="utf-8",
    )
    (package / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    ignored = workdir / ".venv"
    ignored.mkdir()
    (ignored / "skip.py").write_text("def skipped():\n    return False\n", encoding="utf-8")

    ctx = PipelineContext(repo_id=str(uuid4()), repo_url="file:///unused", workdir=str(workdir))
    parsed_ctx = await parse.run(ctx)
    chunked_ctx = await chunk.run(parsed_ctx)

    assert parsed_ctx.files == ["pkg/example.py"]
    assert len(parsed_ctx.parsed_files) == 1
    assert len(parsed_ctx.warnings) == 1
    assert "bad.py" in parsed_ctx.warnings[0]

    chunks = {(item.chunk_type, item.symbol_name): item for item in chunked_ctx.chunks}
    assert set(chunks) == {
        (ChunkType.module_doc, "__module_doc__"),
        (ChunkType.function, "top"),
        (ChunkType.class_, "Greeter"),
        (ChunkType.method, "hello"),
        (ChunkType.method, "goodbye"),
    }

    top = chunks[(ChunkType.function, "top")]
    assert top.file_path == "pkg/example.py"
    assert top.signature == "def top(a: int) -> str"
    assert top.start_line == 6
    assert top.end_line == 8
    assert top.imports == [
        "import os",
        "from collections import defaultdict as dd",
        "import json",
    ]

    klass = chunks[(ChunkType.class_, "Greeter")]
    assert klass.signature == "class Greeter"
    assert klass.start_line == 11
    assert klass.end_line == 18
    assert "def hello" in klass.content

    hello = chunks[(ChunkType.method, "hello")]
    assert hello.parent_symbol == "Greeter"
    assert hello.start_line == 14
    assert hello.end_line == 15


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "Dcode Test",
            "GIT_AUTHOR_EMAIL": "dcode@example.com",
            "GIT_COMMITTER_NAME": "Dcode Test",
            "GIT_COMMITTER_EMAIL": "dcode@example.com",
        },
        text=True,
    )
    return result.stdout
