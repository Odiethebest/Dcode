# Dcode Index Worker image.
# Build context: repo root.
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

RUN uv sync --no-dev

CMD ["uv", "run", "--package", "dcode-worker", "python", "-m", "dcode_worker.main"]
