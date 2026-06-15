"""Shared state passed through every indexing pipeline stage.

Lives in its own module to break the import cycle between pipeline.py and
the stage modules. Each stage takes a PipelineContext and returns an
updated one — pure-functional dataflow.
"""

from dataclasses import dataclass, field
from typing import Any

from dcode_worker.models import CodeChunk, ParsedPythonFile


@dataclass
class PipelineContext:
    repo_id: str
    repo_url: str
    workdir: str | None = None
    commit_sha: str | None = None
    files: list[str] = field(default_factory=list)
    parsed_files: list[ParsedPythonFile] = field(default_factory=list)
    chunks: list[CodeChunk] = field(default_factory=list)
    symbols: list[Any] = field(default_factory=list)
    edges: list[Any] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
