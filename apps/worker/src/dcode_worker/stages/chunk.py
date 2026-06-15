"""Pipeline stage: AST-level chunking at semantic Python boundaries."""

import ast

from dcode_shared.schemas import ChunkType

from dcode_worker.context import PipelineContext
from dcode_worker.models import CodeChunk, ParsedPythonFile


async def run(ctx: PipelineContext) -> PipelineContext:
    """Emit chunks for module docstrings, functions, classes, and methods."""
    if not ctx.parsed_files:
        ctx.chunks = []
        return ctx

    chunks: list[CodeChunk] = []
    for parsed_file in ctx.parsed_files:
        chunks.extend(_chunks_for_file(parsed_file))

    ctx.chunks = sorted(chunks, key=lambda item: (item.file_path, item.start_line, item.end_line))
    return ctx


def _chunks_for_file(parsed_file: ParsedPythonFile) -> list[CodeChunk]:
    source_lines = parsed_file.source.splitlines()
    chunks: list[CodeChunk] = []

    module_doc = _module_doc_chunk(parsed_file, source_lines)
    if module_doc is not None:
        chunks.append(module_doc)

    for node in parsed_file.tree.body:
        if isinstance(node, ast.ClassDef):
            chunks.append(_class_chunk(parsed_file, source_lines, node))
            chunks.extend(_method_chunks(parsed_file, source_lines, node))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            chunks.append(_function_chunk(parsed_file, source_lines, node, parent_symbol=None))

    return chunks


def _module_doc_chunk(parsed_file: ParsedPythonFile, source_lines: list[str]) -> CodeChunk | None:
    if not parsed_file.tree.body:
        return None
    first = parsed_file.tree.body[0]
    if not (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return None

    return CodeChunk(
        file_path=parsed_file.file_path,
        chunk_type=ChunkType.module_doc,
        parent_symbol=None,
        symbol_name="__module_doc__",
        signature=None,
        start_line=first.lineno,
        end_line=_end_line(first),
        imports=parsed_file.imports,
        content=_source_segment(source_lines, first.lineno, _end_line(first)),
    )


def _class_chunk(
    parsed_file: ParsedPythonFile, source_lines: list[str], node: ast.ClassDef
) -> CodeChunk:
    return CodeChunk(
        file_path=parsed_file.file_path,
        chunk_type=ChunkType.class_,
        parent_symbol=None,
        symbol_name=node.name,
        signature=_signature(source_lines, node),
        start_line=node.lineno,
        end_line=_end_line(node),
        imports=_imports_for_node(parsed_file.imports, node),
        content=_source_segment(source_lines, node.lineno, _end_line(node)),
    )


def _method_chunks(
    parsed_file: ParsedPythonFile,
    source_lines: list[str],
    class_node: ast.ClassDef,
) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            chunks.append(
                _function_chunk(parsed_file, source_lines, node, parent_symbol=class_node.name)
            )
    return chunks


def _function_chunk(
    parsed_file: ParsedPythonFile,
    source_lines: list[str],
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    parent_symbol: str | None,
) -> CodeChunk:
    return CodeChunk(
        file_path=parsed_file.file_path,
        chunk_type=ChunkType.method if parent_symbol is not None else ChunkType.function,
        parent_symbol=parent_symbol,
        symbol_name=node.name,
        signature=_signature(source_lines, node),
        start_line=node.lineno,
        end_line=_end_line(node),
        imports=_imports_for_node(parsed_file.imports, node),
        content=_source_segment(source_lines, node.lineno, _end_line(node)),
    )


def _imports_for_node(module_imports: list[str], node: ast.AST) -> list[str]:
    imports = list(module_imports)
    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            imports.extend(f"import {_format_alias(alias)}" for alias in child.names)
        elif isinstance(child, ast.ImportFrom):
            module = "." * child.level + (child.module or "")
            imports.extend(f"from {module} import {_format_alias(alias)}" for alias in child.names)
    return list(dict.fromkeys(imports))


def _signature(
    source_lines: list[str],
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    line = source_lines[node.lineno - 1].strip()
    return line.removesuffix(":")


def _source_segment(source_lines: list[str], start_line: int, end_line: int) -> str:
    return "\n".join(source_lines[start_line - 1 : end_line])


def _end_line(node: ast.AST) -> int:
    end_lineno = getattr(node, "end_lineno", None)
    if isinstance(end_lineno, int):
        return end_lineno
    lineno = getattr(node, "lineno", None)
    if isinstance(lineno, int):
        return lineno
    raise TypeError(f"AST node has no line number: {node.__class__.__name__}")


def _format_alias(alias: ast.alias) -> str:
    if alias.asname is None:
        return alias.name
    return f"{alias.name} as {alias.asname}"
