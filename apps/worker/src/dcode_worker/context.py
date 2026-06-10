"""Shared state passed through every indexing pipeline stage.

Lives in its own module to break the import cycle between pipeline.py and
the stage modules. Each stage takes a PipelineContext and returns an
updated one — pure-functional dataflow.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    repo_id: str
    repo_url: str
    workdir: str | None = None
    files: list[str] = field(default_factory=list)
    chunks: list[Any] = field(default_factory=list)
    symbols: list[Any] = field(default_factory=list)
    edges: list[Any] = field(default_factory=list)
    error: str | None = None
