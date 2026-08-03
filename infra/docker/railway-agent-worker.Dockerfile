# Dcode agent + index worker in one image — Railway only.
#
# Deploy.md R-1: a Railway volume attaches to exactly one service, and the
# worker writes the repository tree the agent's file tools read. The two
# processes that share that volume therefore share a container.
#
# `docker-compose.yml` still runs them as two services against a shared Docker
# volume, and this file is not referenced there. The local path is not degraded
# to match the constrained one (Deploy.md §5.1).
#
# Build context: repo root.
FROM python:3.11-slim

# ripgrep for the agent's grep tool; git for the worker's clone stage. Two
# images' worth of dependencies, because this is two services.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep git curl \
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

# Both packages, and only those two. The workspace also contains the torch-
# dependent model sidecars, which this image does not run — see api.Dockerfile.
RUN uv sync --no-dev --package dcode-agent --package dcode-worker

COPY infra/docker/railway-agent-worker-entrypoint.sh /usr/local/bin/dcode-entrypoint
RUN chmod +x /usr/local/bin/dcode-entrypoint

# Railway injects PORT. 8001 keeps the local default meaningful.
ENV PORT=8001
EXPOSE 8001

CMD ["/usr/local/bin/dcode-entrypoint"]
