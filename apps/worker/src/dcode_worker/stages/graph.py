"""Pipeline stage: build the first-pass AST code graph."""

import ast
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from dcode_shared.db.models import Chunk as DBChunk
from dcode_shared.db.models import Edge, Symbol
from dcode_shared.db.session import SessionLocal
from dcode_shared.schemas import ChunkType, EdgeType, SymbolKind
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcode_worker.context import PipelineContext
from dcode_worker.models import ParsedPythonFile

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@dataclass(frozen=True)
class SymbolRecord:
    qualified_name: str
    kind: SymbolKind
    file_path: str
    line: int
    chunk_lookup: tuple[str, str, str | None, int] | None


@dataclass(frozen=True)
class ImportRecord:
    source_module: str
    target_module: str
    line: int


async def run(
    ctx: PipelineContext,
    *,
    session_factory: SessionFactory = SessionLocal,
) -> PipelineContext:
    """Persist module/function/class/method symbols and internal import edges."""
    repo_id = UUID(ctx.repo_id)
    module_by_file = {
        parsed.file_path: _module_name(parsed.file_path) for parsed in ctx.parsed_files
    }
    internal_modules = set(module_by_file.values())

    symbol_records: list[SymbolRecord] = []
    import_records: list[ImportRecord] = []
    for parsed_file in ctx.parsed_files:
        module_name = module_by_file[parsed_file.file_path]
        symbol_records.extend(_symbols_for_file(parsed_file, module_name))
        import_records.extend(_imports_for_file(parsed_file, module_name, internal_modules))

    async with session_factory() as db:
        chunks = await _load_chunks(db, repo_id)
        symbols = _build_symbols(repo_id, symbol_records, chunks)
        symbol_by_qname = {symbol.qualified_name: symbol for symbol in symbols}
        edges = _build_edges(repo_id, import_records, symbol_by_qname)

        await db.execute(delete(Edge).where(Edge.repo_id == repo_id))
        await db.execute(delete(Symbol).where(Symbol.repo_id == repo_id))
        db.add_all(symbols)
        await db.flush()
        db.add_all(edges)
        await db.commit()

    ctx.symbols = symbols
    ctx.edges = edges
    return ctx


def _symbols_for_file(parsed_file: ParsedPythonFile, module_name: str) -> list[SymbolRecord]:
    records = [
        SymbolRecord(
            qualified_name=module_name,
            kind=SymbolKind.module,
            file_path=parsed_file.file_path,
            line=1,
            chunk_lookup=None,
        )
    ]

    for node in parsed_file.tree.body:
        if isinstance(node, ast.ClassDef):
            records.append(
                SymbolRecord(
                    qualified_name=f"{module_name}.{node.name}",
                    kind=SymbolKind.class_,
                    file_path=parsed_file.file_path,
                    line=node.lineno,
                    chunk_lookup=(ChunkType.class_.value, node.name, None, node.lineno),
                )
            )
            for child in node.body:
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    records.append(
                        SymbolRecord(
                            qualified_name=f"{module_name}.{node.name}.{child.name}",
                            kind=SymbolKind.method,
                            file_path=parsed_file.file_path,
                            line=child.lineno,
                            chunk_lookup=(
                                ChunkType.method.value,
                                child.name,
                                node.name,
                                child.lineno,
                            ),
                        )
                    )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            records.append(
                SymbolRecord(
                    qualified_name=f"{module_name}.{node.name}",
                    kind=SymbolKind.function,
                    file_path=parsed_file.file_path,
                    line=node.lineno,
                    chunk_lookup=(ChunkType.function.value, node.name, None, node.lineno),
                )
            )

    return records


def _imports_for_file(
    parsed_file: ParsedPythonFile,
    module_name: str,
    internal_modules: set[str],
) -> list[ImportRecord]:
    imports: list[ImportRecord] = []
    for node in parsed_file.tree.body:
        for target in _internal_import_targets(node, module_name, internal_modules):
            imports.append(
                ImportRecord(source_module=module_name, target_module=target, line=node.lineno)
            )
    return _unique_imports(imports)


def _internal_import_targets(
    node: ast.stmt,
    current_module: str,
    internal_modules: set[str],
) -> list[str]:
    if isinstance(node, ast.Import):
        return [
            target
            for alias in node.names
            for target in [_best_internal_module(alias.name, internal_modules)]
            if target is not None
        ]

    if not isinstance(node, ast.ImportFrom):
        return []

    base_module = _resolve_import_from_base(current_module, node)
    targets: list[str] = []
    for alias in node.names:
        candidates = []
        if base_module:
            candidates.append(f"{base_module}.{alias.name}")
            candidates.append(base_module)
        else:
            candidates.append(alias.name)
        for candidate in candidates:
            target = _best_internal_module(candidate, internal_modules)
            if target is not None:
                targets.append(target)
                break
    return targets


def _resolve_import_from_base(current_module: str, node: ast.ImportFrom) -> str:
    module = node.module or ""
    if node.level == 0:
        return module

    package_parts = current_module.split(".")[:-1]
    if node.level > 1:
        package_parts = package_parts[: -(node.level - 1)]
    if module:
        package_parts.extend(module.split("."))
    return ".".join(part for part in package_parts if part)


def _best_internal_module(imported: str, internal_modules: set[str]) -> str | None:
    parts = imported.split(".")
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in internal_modules:
            return candidate
    return None


async def _load_chunks(
    db: AsyncSession, repo_id: UUID
) -> dict[tuple[str, str, str, str | None, int], UUID]:
    result = await db.execute(select(DBChunk).where(DBChunk.repo_id == repo_id))
    chunks = result.scalars().all()
    return {
        (
            chunk.file_path,
            chunk.chunk_type,
            chunk.symbol_name,
            chunk.parent_symbol,
            chunk.start_line,
        ): chunk.id
        for chunk in chunks
    }


def _build_symbols(
    repo_id: UUID,
    records: list[SymbolRecord],
    chunks: dict[tuple[str, str, str, str | None, int], UUID],
) -> list[Symbol]:
    symbols: list[Symbol] = []
    seen: set[str] = set()
    for record in records:
        if record.qualified_name in seen:
            continue
        seen.add(record.qualified_name)

        chunk_id = None
        if record.chunk_lookup is not None:
            chunk_type, symbol_name, parent_symbol, start_line = record.chunk_lookup
            chunk_id = chunks.get(
                (record.file_path, chunk_type, symbol_name, parent_symbol, start_line)
            )

        symbols.append(
            Symbol(
                id=uuid4(),
                repo_id=repo_id,
                qualified_name=record.qualified_name,
                kind=record.kind.value,
                file_path=record.file_path,
                line=record.line,
                chunk_id=chunk_id,
            )
        )
    return symbols


def _build_edges(
    repo_id: UUID,
    imports: list[ImportRecord],
    symbol_by_qname: dict[str, Symbol],
) -> list[Edge]:
    edges: list[Edge] = []
    for record in imports:
        source = symbol_by_qname.get(record.source_module)
        target = symbol_by_qname.get(record.target_module)
        if source is None or target is None or source.id == target.id:
            continue
        edges.append(
            Edge(
                id=uuid4(),
                repo_id=repo_id,
                source_id=source.id,
                target_id=target.id,
                edge_type=EdgeType.imports.value,
                source_line=record.line,
            )
        )
    return edges


def _module_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    without_suffix = path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1] or ["__init__"]
    return ".".join(parts)


def _unique_imports(imports: list[ImportRecord]) -> list[ImportRecord]:
    seen: set[tuple[str, str, int]] = set()
    unique: list[ImportRecord] = []
    for record in imports:
        key = (record.source_module, record.target_module, record.line)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique
