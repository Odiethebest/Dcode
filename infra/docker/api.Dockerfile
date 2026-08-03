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

RUN uv sync --no-dev

EXPOSE 8000

# HOST and PORT are read at start, not baked. Railway injects PORT and its
# private network is IPv6, so a service that binds 0.0.0.0 there is reachable
# by nothing. The defaults are the previous literals, so compose is unchanged
# — `sh -c exec` keeps uvicorn as the container's main process rather than
# leaving a shell in front of it to swallow signals.
CMD ["sh", "-c", "exec uv run --package dcode-api uvicorn dcode_api.main:app \
  --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
