# Dcode embedding sidecar — loads OD-2 model and exposes POST /embed.
# Build context: repo root.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
COPY packages ./packages
COPY apps/embedding ./apps/embedding

RUN uv sync --no-dev --package dcode-embedding

ENV EMBEDDING_MODEL_NAME=jinaai/jina-embeddings-v2-base-code
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV PYTORCH_ENABLE_MPS_FALLBACK=0

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=180s \
    CMD curl -fsS http://localhost:8002/healthz || exit 1

# Use the synced venv directly — avoid `uv run` reinstalling packages on restart.
CMD ["/app/.venv/bin/uvicorn", "dcode_embedding.main:app", "--host", "0.0.0.0", "--port", "8002"]
