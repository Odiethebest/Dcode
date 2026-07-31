"""AST graph stage tests."""

import ast
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import TracebackType
from uuid import UUID, uuid4

from dcode_shared.db.models import Chunk as DBChunk
from dcode_shared.db.models import Edge, Symbol
from dcode_shared.schemas import EdgeType, SymbolKind
from dcode_worker.context import PipelineContext
from dcode_worker.models import CodeChunk, ParsedPythonFile
from dcode_worker.stages import chunk, graph, parse
from sqlalchemy.ext.asyncio import AsyncSession


async def test_graph_stage_persists_symbols_edges_and_chunk_links(tmp_path: Path) -> None:
    workdir = tmp_path / "repo"
    package = workdir / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "alpha.py").write_text(
        """from . import beta
import os


class Alpha:
    def method(self) -> None:
        return None


def top() -> str:
    return beta.helper()
""",
        encoding="utf-8",
    )
    (package / "beta.py").write_text(
        """def helper() -> str:
    return "ok"
""",
        encoding="utf-8",
    )
    repo_id = uuid4()
    ctx = PipelineContext(repo_id=str(repo_id), repo_url="file:///unused", workdir=str(workdir))
    ctx = await parse.run(ctx)
    ctx = await chunk.run(ctx)
    db_chunks = [_db_chunk(repo_id, item) for item in ctx.chunks]
    session_factory = FakeSessionFactory(db_chunks)

    result = await graph.run(ctx, session_factory=session_factory)

    symbols = {symbol.qualified_name: symbol for symbol in session_factory.session.symbols}
    assert set(symbols) == {
        "pkg",
        "pkg.alpha",
        "pkg.alpha.Alpha",
        "pkg.alpha.Alpha.method",
        "pkg.alpha.top",
        "pkg.beta",
        "pkg.beta.helper",
    }
    assert symbols["pkg.alpha"].kind == SymbolKind.module.value
    assert symbols["pkg.alpha.Alpha"].kind == SymbolKind.class_.value
    assert symbols["pkg.alpha.Alpha.method"].kind == SymbolKind.method.value
    assert symbols["pkg.alpha.top"].kind == SymbolKind.function.value
    assert symbols["pkg.alpha"].repo_id == repo_id
    assert symbols["pkg.alpha.Alpha"].chunk_id is not None
    assert symbols["pkg.alpha.Alpha.method"].chunk_id is not None
    assert symbols["pkg.alpha.top"].chunk_id is not None

    edges = session_factory.session.edges
    assert len(edges) == 2
    import_edges = [edge for edge in edges if edge.edge_type == EdgeType.imports.value]
    call_edges = [edge for edge in edges if edge.edge_type == EdgeType.calls.value]
    assert len(import_edges) == 1
    assert len(call_edges) == 1
    assert import_edges[0].repo_id == repo_id
    assert import_edges[0].source_id == symbols["pkg.alpha"].id
    assert import_edges[0].target_id == symbols["pkg.beta"].id
    assert import_edges[0].source_line == 1
    assert call_edges[0].source_id == symbols["pkg.alpha.top"].id
    assert call_edges[0].target_id == symbols["pkg.beta.helper"].id

    assert result.symbols == session_factory.session.symbols
    assert result.edges == session_factory.session.edges
    assert session_factory.session.commits == 1
    assert session_factory.session.flushes == 1
    assert session_factory.session.delete_calls == 2


def test_graph_symbol_building_deduplicates_qualified_names() -> None:
    records = [
        graph.SymbolRecord("pkg.mod.fn", SymbolKind.function, "pkg/mod.py", 1, None),
        graph.SymbolRecord("pkg.mod.fn", SymbolKind.function, "pkg/mod.py", 20, None),
    ]

    symbols = graph._build_symbols(uuid4(), records, {})

    assert len(symbols) == 1
    assert symbols[0].qualified_name == "pkg.mod.fn"
    assert symbols[0].line == 1


def test_resolve_call_target_handles_imported_attribute_call() -> None:
    internal_symbols = {"pkg.alpha.top", "pkg.beta.helper"}
    aliases = {"beta": "pkg.beta"}
    target = graph._resolve_call_target(
        ast.Attribute(value=ast.Name(id="beta", ctx=ast.Load()), attr="helper", ctx=ast.Load()),
        module_name="pkg.alpha",
        class_name=None,
        local_functions=set(),
        import_aliases=aliases,
        internal_symbols=internal_symbols,
    )
    assert target == "pkg.beta.helper"


def test_resolve_call_target_handles_self_method_call() -> None:
    internal_symbols = {"pkg.alpha.Alpha.method", "pkg.alpha.Alpha.other"}
    target = graph._resolve_call_target(
        ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr="other", ctx=ast.Load()),
        module_name="pkg.alpha",
        class_name="Alpha",
        local_functions=set(),
        import_aliases={},
        internal_symbols=internal_symbols,
    )
    assert target == "pkg.alpha.Alpha.other"


async def test_graph_stage_builds_inherits_and_references_edges(tmp_path: Path) -> None:
    workdir = tmp_path / "repo"
    package = workdir / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "base.py").write_text("class Base:\n    pass\n", encoding="utf-8")
    (package / "impl.py").write_text(
        """from .base import Base


class Impl(Base):
    pass


def make() -> type[Base]:
    return Impl
""",
        encoding="utf-8",
    )
    repo_id = uuid4()
    ctx = PipelineContext(repo_id=str(repo_id), repo_url="file:///unused", workdir=str(workdir))
    ctx = await parse.run(ctx)
    ctx = await chunk.run(ctx)
    session_factory = FakeSessionFactory([_db_chunk(repo_id, item) for item in ctx.chunks])

    await graph.run(ctx, session_factory=session_factory)

    symbols = {symbol.qualified_name: symbol for symbol in session_factory.session.symbols}
    edges = session_factory.session.edges
    inherits = [edge for edge in edges if edge.edge_type == EdgeType.inherits.value]
    references = [edge for edge in edges if edge.edge_type == EdgeType.references.value]

    # `class Impl(Base)` → one inherits edge Impl → Base.
    assert len(inherits) == 1
    assert inherits[0].source_id == symbols["pkg.impl.Impl"].id
    assert inherits[0].target_id == symbols["pkg.base.Base"].id

    # `make` uses `Impl` as a return value and `Base` in its annotation → references
    # (not calls); the module reference to `pkg.base` stays an import edge only.
    ref_pairs = {(edge.source_id, edge.target_id) for edge in references}
    assert (symbols["pkg.impl.make"].id, symbols["pkg.impl.Impl"].id) in ref_pairs
    assert (symbols["pkg.impl.make"].id, symbols["pkg.base.Base"].id) in ref_pairs
    assert all(edge.source_id != edge.target_id for edge in references)


def test_resolve_base_handles_local_and_imported_bases() -> None:
    internal = {"pkg.m.Base", "pkg.m.Child", "pkg.other.Mixin"}
    local = graph._resolve_base(
        ast.Name(id="Base", ctx=ast.Load()),
        module_name="pkg.m",
        local_classes={"Base", "Child"},
        import_aliases={},
        internal_symbols=internal,
    )
    imported = graph._resolve_base(
        ast.Attribute(value=ast.Name(id="other", ctx=ast.Load()), attr="Mixin", ctx=ast.Load()),
        module_name="pkg.m",
        local_classes=set(),
        import_aliases={"other": "pkg.other"},
        internal_symbols=internal,
    )
    external = graph._resolve_base(
        ast.Name(id="External", ctx=ast.Load()),
        module_name="pkg.m",
        local_classes=set(),
        import_aliases={},
        internal_symbols=internal,
    )
    assert local == "pkg.m.Base"
    assert imported == "pkg.other.Mixin"
    assert external is None


def _db_chunk(repo_id: UUID, item: CodeChunk) -> DBChunk:
    return DBChunk(
        id=uuid4(),
        repo_id=repo_id,
        file_path=item.file_path,
        chunk_type=item.chunk_type.value,
        parent_symbol=item.parent_symbol,
        symbol_name=item.symbol_name,
        signature=item.signature,
        start_line=item.start_line,
        end_line=item.end_line,
        imports=item.imports,
        content=item.content,
        embedding=[0.0],
    )


class FakeExecuteResult:
    def __init__(self, chunks: list[DBChunk]) -> None:
        self.chunks = chunks

    def scalars(self) -> "FakeExecuteResult":
        return self

    def all(self) -> list[DBChunk]:
        return self.chunks


class FakeSession(AbstractAsyncContextManager[AsyncSession]):
    def __init__(self, chunks: list[DBChunk]) -> None:
        self.chunks = chunks
        self.symbols: list[Symbol] = []
        self.edges: list[Edge] = []
        self.commits = 0
        self.flushes = 0
        self.delete_calls = 0

    async def __aenter__(self) -> AsyncSession:
        return self  # type: ignore[return-value]

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def execute(self, statement: object) -> FakeExecuteResult:
        if statement.__class__.__name__ == "Delete":
            self.delete_calls += 1
        return FakeExecuteResult(self.chunks)

    def add_all(self, rows: list[object]) -> None:
        for row in rows:
            if isinstance(row, Symbol):
                self.symbols.append(row)
            elif isinstance(row, Edge):
                self.edges.append(row)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


class FakeSessionFactory:
    def __init__(self, chunks: list[DBChunk]) -> None:
        self.session = FakeSession(chunks)

    def __call__(self) -> AbstractAsyncContextManager[AsyncSession]:
        return self.session


# ---------------------------------------------------------------------------
# Call resolution beyond the same class body
# ---------------------------------------------------------------------------


def _call_targets(source: str, module_name: str, extra_symbols: set[str]) -> set[str]:
    """Resolve calls in one synthetic module, with inheritance available."""
    parsed = ParsedPythonFile(
        file_path=f"{module_name.replace('.', '/')}.py",
        source=source,
        tree=ast.parse(source),
    )
    internal_symbols = extra_symbols
    inherits = graph._inherits_for_file(
        parsed,
        module_name,
        internal_symbols=internal_symbols,
        internal_modules={module_name},
    )
    records = graph._calls_for_file(
        parsed,
        module_name,
        internal_symbols=internal_symbols,
        internal_modules={module_name},
        bases_by_class=graph._bases_by_class(inherits),
    )
    return {record.target_symbol for record in records}


def test_self_call_resolves_through_a_base_class() -> None:
    """The miss that hid the whole redirect machinery from Session.

    `resolve_redirects` lives on a mixin, so `self.resolve_redirects()` inside
    `Session.send` used to resolve to nothing at all.
    """
    source = """
class RedirectMixin:
    def resolve_redirects(self):
        return None


class Session(RedirectMixin):
    def send(self):
        return self.resolve_redirects()
"""
    targets = _call_targets(
        source,
        "pkg.sessions",
        {
            "pkg.sessions",
            "pkg.sessions.RedirectMixin",
            "pkg.sessions.RedirectMixin.resolve_redirects",
            "pkg.sessions.Session",
            "pkg.sessions.Session.send",
        },
    )

    assert "pkg.sessions.RedirectMixin.resolve_redirects" in targets


def test_own_method_still_wins_over_an_inherited_one_of_the_same_name() -> None:
    """Nearest definition, not just any definition."""
    source = """
class Base:
    def handle(self):
        return None


class Child(Base):
    def handle(self):
        return None

    def run(self):
        return self.handle()
"""
    targets = _call_targets(
        source,
        "pkg.mod",
        {
            "pkg.mod",
            "pkg.mod.Base",
            "pkg.mod.Base.handle",
            "pkg.mod.Child",
            "pkg.mod.Child.handle",
            "pkg.mod.Child.run",
        },
    )

    assert "pkg.mod.Child.handle" in targets
    assert "pkg.mod.Base.handle" not in targets


def test_a_locally_constructed_object_resolves_its_method_calls() -> None:
    """`p = PreparedRequest()` then `p.prepare()` — how these flows are written."""
    source = """
class PreparedRequest:
    def prepare(self):
        return None


class Session:
    def prepare_request(self):
        p = PreparedRequest()
        p.prepare()
        return p
"""
    targets = _call_targets(
        source,
        "pkg.models",
        {
            "pkg.models",
            "pkg.models.PreparedRequest",
            "pkg.models.PreparedRequest.prepare",
            "pkg.models.Session",
            "pkg.models.Session.prepare_request",
        },
    )

    assert "pkg.models.PreparedRequest.prepare" in targets


def test_a_reassigned_local_is_not_given_a_type() -> None:
    """Two constructors for one name is ambiguous; guessing would invent an edge."""
    source = """
class Alpha:
    def go(self):
        return None


class Beta:
    def go(self):
        return None


class Runner:
    def run(self, flag):
        handler = Alpha()
        handler = Beta()
        return handler.go()
"""
    targets = _call_targets(
        source,
        "pkg.mod",
        {
            "pkg.mod",
            "pkg.mod.Alpha",
            "pkg.mod.Alpha.go",
            "pkg.mod.Beta",
            "pkg.mod.Beta.go",
            "pkg.mod.Runner",
            "pkg.mod.Runner.run",
        },
    )

    assert "pkg.mod.Alpha.go" not in targets
    assert "pkg.mod.Beta.go" not in targets


def test_a_cyclic_hierarchy_does_not_stall_resolution() -> None:
    assert (
        graph._resolve_self_attribute(
            "pkg.A",
            "missing",
            internal_symbols={"pkg.A", "pkg.B"},
            bases_by_class={"pkg.A": ["pkg.B"], "pkg.B": ["pkg.A"]},
        )
        is None
    )
