"""Pipeline stage: tree-sitter Python AST parsing.

Implements DESIGN.md §2.1 'Parse' stage. Produces AST nodes that the
chunk stage consumes; populates ctx.files with discovered .py paths.
"""

from dcode_worker.context import PipelineContext


async def run(ctx: PipelineContext) -> PipelineContext:
    # TODO(M1): walk ctx.workdir for .py files; parse each via tree-sitter
    #           Python grammar; attach AST roots to ctx (or pass through chunks).
    raise NotImplementedError("parse stage — implement per DESIGN.md §2.1 at M1")
