# Dcode Agent Orchestrator image.
# Build context: repo root.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY apps/agent ./apps/agent
COPY apps/eval ./apps/eval
COPY apps/embedding ./apps/embedding
COPY apps/reranker ./apps/reranker

# Scoped for the same reason as api.Dockerfile: the workspace contains two
# torch-dependent model sidecars this image does not run.
RUN uv sync --no-dev --package dcode-agent

EXPOSE 8001

# The venv binary directly, not `uv run`.
#
# `uv run` re-syncs the environment at container start, and without --no-dev
# that means downloading mypy and ruff every single time. On the first Railway
# deploy it also could not find alembic at all, because the build-time sync had
# installed nothing (see the RUN above). apps/embedding already did it this way
# with a comment saying why; api, worker and agent had not caught up.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn dcode_agent.main:app --host ${HOST:-::} --port ${PORT:-8001}"]
