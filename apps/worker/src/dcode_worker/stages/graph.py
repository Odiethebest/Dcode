"""Pipeline stage: build the code call graph via jedi.

Implements DESIGN.md §2.1 'Graph' stage. Emits Symbol nodes and Edge
records (calls / imports / inherits / references) into Postgres.
"""

from dcode_worker.context import PipelineContext


async def run(ctx: PipelineContext) -> PipelineContext:
    # TODO(M1): for each .py file in ctx.workdir, run jedi to resolve
    #   - definitions (Symbol rows; qualified_name like 'flask.app.Flask.run')
    #   - references (Edge rows of type 'references')
    #   - imports    (Edge rows of type 'imports')
    #   - class bases (Edge rows of type 'inherits')
    # Persist into the symbols / edges tables per DESIGN.md §3.2.
    raise NotImplementedError("graph stage — implement per DESIGN.md §2.1 at M1")
