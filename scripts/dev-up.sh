#!/usr/bin/env bash
# Bring up the full Dcode stack locally and run migrations.
# Idempotent: safe to re-run.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> docker compose up --build"
docker compose up -d --build

echo "==> waiting for healthchecks..."
sleep 6
docker compose ps

echo "==> applying database migrations"
make migrate || echo "    (migration failed; services may still be starting up)"

cat <<EOF

==> URLs:
    API gateway:  http://localhost:8000/healthz
    Agent:        http://localhost:8001/healthz
    Frontend:     http://localhost:5173
    RabbitMQ UI:  http://localhost:15672  (guest / guest)
    Postgres:     localhost:5432           (dcode / dcode)

EOF
