"""Self-hosted HTTP reranker sidecar for BGE and compatible cross-encoders."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

_model: CrossEncoder | None = None
_model_name: str = ""


class RerankRequest(BaseModel):
    query: str = Field(min_length=1)
    passages: list[str] = Field(min_length=1)


class RerankResponse(BaseModel):
    scores: list[float]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _model, _model_name
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    from sentence_transformers import CrossEncoder

    _model_name = os.environ.get(
        "RERANKER_MODEL_NAME",
        "BAAI/bge-reranker-v2-m3",
    )
    print(f"Loading reranker model: {_model_name} on CPU ...", flush=True)
    _model = CrossEncoder(_model_name, trust_remote_code=True, device="cpu")
    max_length = int(os.environ.get("RERANKER_MAX_SEQ_LENGTH", "512"))
    if max_length > 0:
        _model.max_length = max_length
    print(
        f"Reranker model ready. max_length={_model.max_length}",
        flush=True,
    )
    yield
    _model = None


app = FastAPI(title="Dcode Reranker Sidecar", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "model": _model_name}


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest) -> RerankResponse:
    if _model is None:
        raise RuntimeError("reranker model is not loaded")

    pairs = [(request.query, passage) for passage in request.passages]
    raw_scores = await asyncio.to_thread(
        _model.predict,
        pairs,
        show_progress_bar=False,
    )
    scores = [float(score) for score in raw_scores]
    return RerankResponse(scores=scores)
