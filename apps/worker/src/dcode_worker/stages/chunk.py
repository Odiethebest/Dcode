"""Pipeline stage: AST-level chunking.

Implements DESIGN.md §2.1 'Chunk' stage. Per D-2.1.1, fixed-window
sliding is **forbidden** — chunks are cut at function / method / class /
module-doc boundaries so that import context and call-site semantics
are preserved.
"""

from dcode_worker.context import PipelineContext


async def run(ctx: PipelineContext) -> PipelineContext:
    # TODO(M1): traverse AST nodes, emit one chunk per
    #           function / method / class / module-doc per D-2.1.1.
    #           Each chunk carries file_path, symbol_name, signature,
    #           start_line, end_line, imports, content.
    raise NotImplementedError("chunk stage — implement per DESIGN.md §2.1 at M1")
