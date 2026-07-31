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


@dataclass(frozen=True)
class CallRecord:
    source_symbol: str
    target_symbol: str
    line: int


@dataclass(frozen=True)
class RelationshipRecord:
    """A generic source→target graph relationship (inherits / references)."""

    source_symbol: str
    target_symbol: str
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

    internal_symbols = {record.qualified_name for record in symbol_records}

    # Inheritance is resolved first because call resolution depends on it. A
    # `self.method()` whose method lives on a base class is the single most
    # common call this analysis used to miss: in `requests` it hides the entire
    # redirect machinery from `Session`, because `resolve_redirects` and friends
    # are defined on `SessionRedirectMixin`.
    inherit_records: list[RelationshipRecord] = []
    for parsed_file in ctx.parsed_files:
        inherit_records.extend(
            _inherits_for_file(
                parsed_file,
                module_by_file[parsed_file.file_path],
                internal_symbols=internal_symbols,
                internal_modules=internal_modules,
            )
        )
    bases_by_class = _bases_by_class(inherit_records)

    call_records: list[CallRecord] = []
    reference_records: list[RelationshipRecord] = []
    for parsed_file in ctx.parsed_files:
        module_name = module_by_file[parsed_file.file_path]
        call_records.extend(
            _calls_for_file(
                parsed_file,
                module_name,
                internal_symbols=internal_symbols,
                internal_modules=internal_modules,
                bases_by_class=bases_by_class,
            )
        )
        reference_records.extend(
            _references_for_file(
                parsed_file,
                module_name,
                internal_symbols=internal_symbols,
                internal_modules=internal_modules,
            )
        )

    async with session_factory() as db:
        chunks = await _load_chunks(db, repo_id)
        symbols = _build_symbols(repo_id, symbol_records, chunks)
        symbol_by_qname = {symbol.qualified_name: symbol for symbol in symbols}
        edges = _build_import_edges(repo_id, import_records, symbol_by_qname)
        edges.extend(_build_call_edges(repo_id, call_records, symbol_by_qname))
        edges.extend(
            _build_relationship_edges(repo_id, inherit_records, symbol_by_qname, EdgeType.inherits)
        )
        edges.extend(
            _build_relationship_edges(
                repo_id, reference_records, symbol_by_qname, EdgeType.references
            )
        )

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


def _calls_for_file(
    parsed_file: ParsedPythonFile,
    module_name: str,
    *,
    internal_symbols: set[str],
    internal_modules: set[str],
    bases_by_class: dict[str, list[str]] | None = None,
) -> list[CallRecord]:
    aliases = _import_aliases_for_file(parsed_file, module_name, internal_modules)
    local_functions = _module_local_function_names(parsed_file)
    local_classes = _module_local_class_names(parsed_file)
    calls: list[CallRecord] = []

    for node in parsed_file.tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            for child in node.body:
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    caller = f"{module_name}.{class_name}.{child.name}"
                    calls.extend(
                        _calls_in_body(
                            child,
                            caller=caller,
                            module_name=module_name,
                            class_name=class_name,
                            local_functions=local_functions,
                            import_aliases=aliases,
                            internal_symbols=internal_symbols,
                            bases_by_class=bases_by_class or {},
                            local_classes=local_classes,
                        )
                    )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            caller = f"{module_name}.{node.name}"
            calls.extend(
                _calls_in_body(
                    node,
                    caller=caller,
                    module_name=module_name,
                    class_name=None,
                    local_functions=local_functions,
                    import_aliases=aliases,
                    internal_symbols=internal_symbols,
                    bases_by_class=bases_by_class or {},
                    local_classes=local_classes,
                )
            )

    return _unique_calls(calls)


def _calls_in_body(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    caller: str,
    module_name: str,
    class_name: str | None,
    local_functions: set[str],
    import_aliases: dict[str, str],
    internal_symbols: set[str],
    bases_by_class: dict[str, list[str]],
    local_classes: set[str],
) -> list[CallRecord]:
    calls: list[CallRecord] = []
    local_types = _local_variable_types(
        node,
        module_name=module_name,
        local_classes=local_classes,
        import_aliases=import_aliases,
        internal_symbols=internal_symbols,
    )
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = _resolve_call_target(
            child.func,
            module_name=module_name,
            class_name=class_name,
            local_functions=local_functions,
            import_aliases=import_aliases,
            internal_symbols=internal_symbols,
            bases_by_class=bases_by_class,
            local_types=local_types,
        )
        if target is None:
            continue
        calls.append(CallRecord(source_symbol=caller, target_symbol=target, line=child.lineno))
    return calls


def _resolve_call_target(
    func: ast.expr,
    *,
    module_name: str,
    class_name: str | None,
    local_functions: set[str],
    import_aliases: dict[str, str],
    internal_symbols: set[str],
    bases_by_class: dict[str, list[str]] | None = None,
    local_types: dict[str, str] | None = None,
) -> str | None:
    if isinstance(func, ast.Name):
        if func.id in import_aliases:
            candidate = import_aliases[func.id]
            return candidate if candidate in internal_symbols else None
        if func.id in local_functions:
            candidate = f"{module_name}.{func.id}"
            return candidate if candidate in internal_symbols else None
        return None

    if not isinstance(func, ast.Attribute):
        return None

    if isinstance(func.value, ast.Name) and func.value.id == "self" and class_name is not None:
        return _resolve_self_attribute(
            f"{module_name}.{class_name}",
            func.attr,
            internal_symbols=internal_symbols,
            bases_by_class=bases_by_class or {},
        )

    # `p = PreparedRequest()` then `p.prepare(...)`. Only a directly constructed
    # local counts: the class is written at the assignment, so this reads the
    # code rather than inferring a type.
    if isinstance(func.value, ast.Name) and local_types and func.value.id in local_types:
        candidate = f"{local_types[func.value.id]}.{func.attr}"
        if candidate in internal_symbols:
            return candidate
        inherited = _resolve_self_attribute(
            local_types[func.value.id],
            func.attr,
            internal_symbols=internal_symbols,
            bases_by_class=bases_by_class or {},
        )
        if inherited is not None:
            return inherited

    prefix: str | None = None
    if isinstance(func.value, ast.Name):
        if func.value.id in import_aliases:
            prefix = import_aliases[func.value.id]
        elif func.value.id in local_functions:
            prefix = f"{module_name}.{func.value.id}"
    elif isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name):
        base_name = func.value.value.id
        if base_name in import_aliases:
            prefix = f"{import_aliases[base_name]}.{func.value.attr}"

    if prefix is None:
        return None

    candidate = f"{prefix}.{func.attr}"
    return candidate if candidate in internal_symbols else None


def _bases_by_class(inherit_records: list[RelationshipRecord]) -> dict[str, list[str]]:
    """Direct internal base classes, keyed by qualified class name."""
    bases: dict[str, list[str]] = {}
    for record in inherit_records:
        bases.setdefault(record.source_symbol, []).append(record.target_symbol)
    return bases


# Depth ceiling for the base-class walk. Deep enough for the mixin stacks this
# analysis meets in practice, shallow enough that a cyclic or pathological
# hierarchy cannot stall indexing.
_MAX_BASE_DEPTH = 6


def _resolve_self_attribute(
    owner: str,
    attribute: str,
    *,
    internal_symbols: set[str],
    bases_by_class: dict[str, list[str]],
) -> str | None:
    """Resolve `self.attr` on `owner`, falling back to its base classes.

    Breadth-first over declared bases, so the nearest definition wins. This is
    an approximation of the MRO, not the MRO itself: it ignores C3
    linearisation, so a diamond with the same name on two branches can resolve
    to the sibling Python would not pick. It is reported as best-effort static
    evidence for that reason.

    Without this, a method inherited from a mixin is invisible to the call
    graph — which in `requests` means `Session.send` appears not to touch the
    redirect machinery at all, because `resolve_redirects` lives on
    `SessionRedirectMixin`.
    """
    own = f"{owner}.{attribute}"
    if own in internal_symbols:
        return own

    seen = {owner}
    frontier = list(bases_by_class.get(owner, ()))
    for _ in range(_MAX_BASE_DEPTH):
        if not frontier:
            return None
        next_frontier: list[str] = []
        for base in frontier:
            if base in seen:
                continue
            seen.add(base)
            candidate = f"{base}.{attribute}"
            if candidate in internal_symbols:
                return candidate
            next_frontier.extend(bases_by_class.get(base, ()))
        frontier = next_frontier
    return None


def _local_variable_types(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    module_name: str,
    local_classes: set[str],
    import_aliases: dict[str, str],
    internal_symbols: set[str],
) -> dict[str, str]:
    """Map local names to the internal class they were directly constructed from.

    Only `name = SomeClass()` counts. The class is written literally at the
    assignment, so this is reading the code rather than inferring a type — the
    stated limit of "no type inference" is intact. A name assigned more than
    once is dropped rather than guessed at.

    This exists because the flows these questions ask about are built that way:
    `Session.prepare_request` does `p = PreparedRequest()` and then `p.prepare(...)`,
    and without this the chain simply stops at the constructor.
    """
    types: dict[str, str] = {}
    reassigned: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Assign) or not isinstance(child.value, ast.Call):
            continue
        resolved = _resolve_base(
            child.value.func,
            module_name=module_name,
            local_classes=local_classes,
            import_aliases=import_aliases,
            internal_symbols=internal_symbols,
        )
        for target in child.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id in types and types[target.id] != resolved:
                reassigned.add(target.id)
            if resolved is not None:
                types[target.id] = resolved
    for name in reassigned:
        types.pop(name, None)
    return types


def _import_aliases_for_file(
    parsed_file: ParsedPythonFile,
    module_name: str,
    internal_modules: set[str],
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in parsed_file.tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                target_module = _best_internal_module(alias.name, internal_modules)
                if target_module is None:
                    continue
                local_name = alias.asname or alias.name.split(".")[0]
                aliases[local_name] = target_module
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        base_module = _resolve_import_from_base(module_name, node)
        for alias in node.names:
            if alias.name == "*":
                continue
            local_name = alias.asname or alias.name
            if base_module and _best_internal_module(base_module, internal_modules):
                aliases[local_name] = f"{base_module}.{alias.name}"
                continue
            target_module = _best_internal_module(alias.name, internal_modules)
            if target_module is not None:
                aliases[local_name] = target_module
    return aliases


def _module_local_function_names(parsed_file: ParsedPythonFile) -> set[str]:
    names: set[str] = set()
    for node in parsed_file.tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
    return names


def _module_local_class_names(parsed_file: ParsedPythonFile) -> set[str]:
    return {node.name for node in parsed_file.tree.body if isinstance(node, ast.ClassDef)}


def _inherits_for_file(
    parsed_file: ParsedPythonFile,
    module_name: str,
    *,
    internal_symbols: set[str],
    internal_modules: set[str],
) -> list[RelationshipRecord]:
    """`inherits` edges from each top-level class to its internal base classes."""
    aliases = _import_aliases_for_file(parsed_file, module_name, internal_modules)
    local_classes = _module_local_class_names(parsed_file)
    records: list[RelationshipRecord] = []
    for node in parsed_file.tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        source = f"{module_name}.{node.name}"
        for base in node.bases:
            target = _resolve_base(
                base,
                module_name=module_name,
                local_classes=local_classes,
                import_aliases=aliases,
                internal_symbols=internal_symbols,
            )
            if target is None or target == source:
                continue
            records.append(
                RelationshipRecord(source_symbol=source, target_symbol=target, line=node.lineno)
            )
    return records


def _resolve_base(
    base: ast.expr,
    *,
    module_name: str,
    local_classes: set[str],
    import_aliases: dict[str, str],
    internal_symbols: set[str],
) -> str | None:
    if isinstance(base, ast.Name):
        if base.id in import_aliases:
            candidate = import_aliases[base.id]
        elif base.id in local_classes:
            candidate = f"{module_name}.{base.id}"
        else:
            return None
        return candidate if candidate in internal_symbols else None

    if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
        alias = import_aliases.get(base.value.id)
        if alias is not None:
            candidate = f"{alias}.{base.attr}"
            return candidate if candidate in internal_symbols else None
    return None


def _references_for_file(
    parsed_file: ParsedPythonFile,
    module_name: str,
    *,
    internal_symbols: set[str],
    internal_modules: set[str],
) -> list[RelationshipRecord]:
    """`references` edges: internal symbols used as a value (not called) inside a
    function/method body — e.g. `x = SomeClass`, `isinstance(o, Cls)`, annotations.

    Module references are skipped (already covered by import edges), as are bare
    call targets (covered by call edges).
    """
    aliases = _import_aliases_for_file(parsed_file, module_name, internal_modules)
    local_symbols = _module_local_function_names(parsed_file) | _module_local_class_names(
        parsed_file
    )
    records: list[RelationshipRecord] = []

    for node in parsed_file.tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    records.extend(
                        _references_in_body(
                            child,
                            caller=f"{module_name}.{node.name}.{child.name}",
                            module_name=module_name,
                            local_symbols=local_symbols,
                            import_aliases=aliases,
                            internal_symbols=internal_symbols,
                            internal_modules=internal_modules,
                        )
                    )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            records.extend(
                _references_in_body(
                    node,
                    caller=f"{module_name}.{node.name}",
                    module_name=module_name,
                    local_symbols=local_symbols,
                    import_aliases=aliases,
                    internal_symbols=internal_symbols,
                    internal_modules=internal_modules,
                )
            )
    return _unique_relationships(records)


def _references_in_body(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    caller: str,
    module_name: str,
    local_symbols: set[str],
    import_aliases: dict[str, str],
    internal_symbols: set[str],
    internal_modules: set[str],
) -> list[RelationshipRecord]:
    call_func_ids = {id(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)}
    references: list[RelationshipRecord] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Name) or not isinstance(child.ctx, ast.Load):
            continue
        if id(child) in call_func_ids:
            continue  # bare-name call target — already covered by call edges
        if child.id in import_aliases:
            candidate = import_aliases[child.id]
        elif child.id in local_symbols:
            candidate = f"{module_name}.{child.id}"
        else:
            continue
        if candidate in internal_modules or candidate not in internal_symbols or candidate == caller:
            continue
        references.append(
            RelationshipRecord(source_symbol=caller, target_symbol=candidate, line=child.lineno)
        )
    return references


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


def _build_import_edges(
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


def _build_call_edges(
    repo_id: UUID,
    calls: list[CallRecord],
    symbol_by_qname: dict[str, Symbol],
) -> list[Edge]:
    edges: list[Edge] = []
    seen: set[tuple[UUID, UUID, int]] = set()
    for record in calls:
        source = symbol_by_qname.get(record.source_symbol)
        target = symbol_by_qname.get(record.target_symbol)
        if source is None or target is None or source.id == target.id:
            continue
        key = (source.id, target.id, record.line)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            Edge(
                id=uuid4(),
                repo_id=repo_id,
                source_id=source.id,
                target_id=target.id,
                edge_type=EdgeType.calls.value,
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


def _unique_calls(calls: list[CallRecord]) -> list[CallRecord]:
    seen: set[tuple[str, str, int]] = set()
    unique: list[CallRecord] = []
    for record in calls:
        key = (record.source_symbol, record.target_symbol, record.line)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _build_relationship_edges(
    repo_id: UUID,
    records: list[RelationshipRecord],
    symbol_by_qname: dict[str, Symbol],
    edge_type: EdgeType,
) -> list[Edge]:
    edges: list[Edge] = []
    seen: set[tuple[UUID, UUID, int]] = set()
    for record in records:
        source = symbol_by_qname.get(record.source_symbol)
        target = symbol_by_qname.get(record.target_symbol)
        if source is None or target is None or source.id == target.id:
            continue
        key = (source.id, target.id, record.line)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            Edge(
                id=uuid4(),
                repo_id=repo_id,
                source_id=source.id,
                target_id=target.id,
                edge_type=edge_type.value,
                source_line=record.line,
            )
        )
    return edges


def _unique_relationships(records: list[RelationshipRecord]) -> list[RelationshipRecord]:
    seen: set[tuple[str, str]] = set()
    unique: list[RelationshipRecord] = []
    for record in records:
        key = (record.source_symbol, record.target_symbol)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique
