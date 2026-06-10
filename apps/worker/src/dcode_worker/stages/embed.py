"""Pipeline stage: batch embedding with Redis content-addressed cache.

Implements DESIGN.md §2.1 'Embed' stage and D-2.1.3 (cache key
`embed:{model_id}:{sha256(text)}`, TTL forever).

The embedding model is Open Decision OD-2 (see PLAN.md §9). We expose an
EmbeddingClient Protocol here so M2 can plug in jina-code / bge-code /
voyage-code without touching this module.
"""

from abc import ABC, abstractmethod

from dcode_worker.context import PipelineContext


class EmbeddingClient(ABC):
    """Abstract client for the configured embedding model (OD-2)."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text. Caller-driven batching."""


class StubEmbeddingClient(EmbeddingClient):
    """Skeleton placeholder — returns zero vectors of the configured dim.

    Lets the pipeline shape be exercised end-to-end without a real model.
    Replaced at M2 once OD-2 is resolved.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]


async def run(ctx: PipelineContext) -> PipelineContext:
    # TODO(M2): per DESIGN.md §2.1:
    #   1. for each chunk, compute embed_cache_key(model_id, content)
    #   2. mget cached vectors from Redis
    #   3. batch-embed the misses via OD-2 client
    #   4. mset new vectors into Redis (TTL forever)
    #   5. attach vectors to chunk records
    raise NotImplementedError("embed stage — implement per DESIGN.md §2.1 at M2")
