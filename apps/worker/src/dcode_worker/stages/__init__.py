"""Clone, parse, chunk, embed, and graph stages for the indexing pipeline.

Each module exposes `async def run(ctx: PipelineContext) -> PipelineContext`.
Stages share no mutable module state; each owns its external side effects and
returns the updated context.
"""

from dcode_worker.stages import chunk, clone, embed, graph, parse

__all__ = ["chunk", "clone", "embed", "graph", "parse"]
