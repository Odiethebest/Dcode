"""Indexing pipeline stages — implements DESIGN.md §2.1 stage table.

Each module exposes `async def run(ctx: PipelineContext) -> PipelineContext`.
Stages are pure-functional: take ctx, return updated ctx; no module state.
"""

from dcode_worker.stages import chunk, clone, embed, graph, parse

__all__ = ["chunk", "clone", "embed", "graph", "parse"]
