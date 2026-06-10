"""Worker import + pipeline shape smoke tests."""

from dcode_worker import pipeline
from dcode_worker.context import PipelineContext
from dcode_worker.stages import chunk, clone, embed, graph, parse


def test_pipeline_context_default_construction() -> None:
    ctx = PipelineContext(repo_id="r", repo_url="https://x.git")
    assert ctx.files == []
    assert ctx.chunks == []
    assert ctx.symbols == []
    assert ctx.edges == []


def test_all_stages_expose_run_coroutine() -> None:
    """Every stage module must expose `run` (filled in at M1/M2)."""
    for mod in (clone, parse, chunk, embed, graph):
        assert callable(getattr(mod, "run"))


async def test_handle_job_tolerates_malformed_message() -> None:
    """Skeleton: malformed JSON must not crash the consumer loop."""
    await pipeline.handle_job(b"not-json")
    await pipeline.handle_job(b'{"missing":"fields"}')


async def test_embedding_stub_returns_zero_vectors_of_configured_dim() -> None:
    stub = embed.StubEmbeddingClient(dim=16)
    vecs = await stub.embed_batch(["a", "b", "c"])
    assert len(vecs) == 3
    assert all(len(v) == 16 for v in vecs)
    assert all(all(x == 0.0 for x in v) for v in vecs)
