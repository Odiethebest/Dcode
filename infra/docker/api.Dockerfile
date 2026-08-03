# Dcode API Gateway image.
# Build context: repo root (workspace resolution needs every member).
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
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
COPY infra/migrations ./infra/migrations

# --package, not the whole workspace.
#
# `uv sync --no-dev` at the workspace root installs EVERY member, and two of
# them — dcode-embedding and dcode-reranker — depend on torch, transformers and
# sentence-transformers. This image runs none of that, and it was pulling
# several GB to sit unused. It was invisible locally because the layer was
# cached; the first clean build took twelve minutes.
#
# The sources are still copied so uv can resolve the workspace; only the
# installation is scoped. alembic is a dcode-api dependency, so the migration
# this image runs before each deploy still has it.
RUN uv sync --no-dev --package dcode-api

EXPOSE 8000

# HOST and PORT are read at start, not baked. Railway injects PORT and its
# private network is IPv6, so a service that binds 0.0.0.0 there is reachable
# by nothing. The defaults are the previous literals, so compose is unchanged
# — `sh -c exec` keeps uvicorn as the container's main process rather than
# leaving a shell in front of it to swallow signals.
# The venv binary directly, not `uv run`.
#
# `uv run` re-syncs the environment at container start, and without --no-dev
# that means downloading mypy and ruff every single time. On the first Railway
# deploy it also could not find alembic at all, because the build-time sync had
# installed nothing (see the RUN above). apps/embedding already did it this way
# with a comment saying why; api, worker and agent had not caught up.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn dcode_api.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
