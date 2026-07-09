# Dcode reranker sidecar — loads OD-3 model and exposes POST /rerank.
# Build context: repo root.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
COPY packages ./packages
COPY apps/reranker ./apps/reranker

RUN uv sync --no-dev --package dcode-reranker

ENV RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV PYTORCH_ENABLE_MPS_FALLBACK=0

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=180s \
    CMD curl -fsS http://localhost:8003/healthz || exit 1

CMD ["/app/.venv/bin/uvicorn", "dcode_reranker.main:app", "--host", "0.0.0.0", "--port", "8003"]
