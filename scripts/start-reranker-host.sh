#!/usr/bin/env bash
# Run the reranker model on the host (recommended on MacBook — avoids Docker OOM).
# API in Docker reaches this via host.docker.internal:8003 (see .env).
set -euo pipefail

cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin:${PATH}"

docker compose stop reranker 2>/dev/null || true

export RERANKER_MODEL_NAME="${RERANKER_MODEL_NAME:-BAAI/bge-reranker-v2-m3}"
export RERANKER_MAX_SEQ_LENGTH="${RERANKER_MAX_SEQ_LENGTH:-512}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export PYTORCH_ENABLE_MPS_FALLBACK=0

echo "==> Loading ${RERANKER_MODEL_NAME} on http://0.0.0.0:8003"
echo "    First run downloads the model — may take several minutes."
echo "    Wait for: Reranker model ready"

exec uv run --python 3.11 --package dcode-reranker \
  uvicorn dcode_reranker.main:app --host 0.0.0.0 --port 8003
