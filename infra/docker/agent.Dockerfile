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
# 0.0.0.0, not `::`. Measured, not assumed: uvicorn given `::` produces an
# IPv6-ONLY socket — an IPv4 connect is refused even though the container has
# net.ipv6.bindv6only=0 — and given 0.0.0.0 the reverse. There is no dual-stack
# option, so this is a choice between them.
#
# Railway's health check arrives over IPv4: with `::` the request never reached
# the application at all and the deploy failed with "1/1 replicas never became
# healthy" while the log showed a perfectly started server. Private networking
# in environments created after 2025-10-16 resolves to both families, so IPv4
# serves both purposes. A legacy IPv6-only environment would need `HOST=::` and
# would then need the health check removed.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn dcode_agent.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8001}"]
