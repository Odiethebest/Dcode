"""Worker-local data records passed between indexing stages."""

import ast
from dataclasses import dataclass, field

from dcode_shared.schemas import ChunkType


@dataclass(frozen=True)
class ParsedPythonFile:
    """A Python file discovered and parsed from a cloned worktree."""

    file_path: str
    source: str
    tree: ast.Module
    imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CodeChunk:
    """AST-boundary chunk metadata ready for embedding and persistence."""

    file_path: str
    chunk_type: ChunkType
    parent_symbol: str | None
    symbol_name: str
    signature: str | None
    start_line: int
    end_line: int
    imports: list[str]
    content: str
