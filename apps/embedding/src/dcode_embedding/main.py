"""Self-hosted embedding sidecar for OD-2 (jina-code and compatible models)."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None
_model_name: str = ""


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _model, _model_name
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    from sentence_transformers import SentenceTransformer

    _model_name = os.environ.get(
        "EMBEDDING_MODEL_NAME",
        "jinaai/jina-embeddings-v2-base-code",
    )
    print(f"Loading embedding model: {_model_name} on CPU ...", flush=True)
    _model = SentenceTransformer(_model_name, trust_remote_code=True, device="cpu")
    print("Embedding model ready.", flush=True)
    yield
    _model = None


app = FastAPI(title="Dcode Embedding Sidecar", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "model": _model_name}


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    if _model is None:
        raise RuntimeError("embedding model is not loaded")

    vectors = await asyncio.to_thread(
        _model.encode,
        request.texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return EmbedResponse(embeddings=vectors.tolist())
