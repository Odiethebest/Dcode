#!/usr/bin/env bash
# Run the embedding model on the host (recommended on MacBook — avoids Docker OOM).
# Worker in Docker reaches this via host.docker.internal:8002 (see .env).
set -euo pipefail

cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin:${PATH}"

docker compose stop embedding 2>/dev/null || true

export EMBEDDING_MODEL_NAME="${EMBEDDING_MODEL_NAME:-jinaai/jina-embeddings-v2-base-code}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export PYTORCH_ENABLE_MPS_FALLBACK=0

echo "==> Loading ${EMBEDDING_MODEL_NAME} on http://0.0.0.0:8002"
echo "    First run downloads the model — may take several minutes."
echo "    Wait for: Application startup complete"

exec uv run --python 3.11 --package dcode-embedding \
  uvicorn dcode_embedding.main:app --host 0.0.0.0 --port 8002
