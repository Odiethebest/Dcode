"""AST graph stage tests."""

from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import TracebackType
from uuid import UUID, uuid4

from dcode_shared.db.models import Chunk as DBChunk
from dcode_shared.db.models import Edge, Symbol
from dcode_shared.schemas import EdgeType, SymbolKind
from dcode_worker.context import PipelineContext
from dcode_worker.models import CodeChunk
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
    assert len(edges) == 1
    assert edges[0].repo_id == repo_id
    assert edges[0].edge_type == EdgeType.imports.value
    assert edges[0].source_id == symbols["pkg.alpha"].id
    assert edges[0].target_id == symbols["pkg.beta"].id
    assert edges[0].source_line == 1

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
