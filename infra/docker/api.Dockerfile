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
COPY infra/migrations ./infra/migrations

RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "--package", "dcode-api", \
     "uvicorn", "dcode_api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
