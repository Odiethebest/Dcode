#!/usr/bin/env bash
# Run the agent and the index worker in one container.
#
# THIS IS A RAILWAY WORKAROUND, NOT AN ARCHITECTURE CHANGE. Deploy.md R-1: a
# Railway volume attaches to exactly one service, and the worker writes the
# cloned repository tree that the agent's read_file / grep / list_directory
# tools read back at query time. Two services cannot share it, so the two
# processes that share the volume share a container.
#
# Locally, Docker shares volumes fine and `docker-compose.yml` keeps them
# separate. Nothing here is used by the developer stack (Deploy.md §5.1).
#
# The durable fix is to stop reading repository source from a filesystem at
# all — Deploy.md §11 item 2 — and it is deliberately not attempted here.
set -euo pipefail

term() {
  # Forward the platform's shutdown to both children rather than letting them
  # be killed individually, so neither is torn down mid-write.
  trap - TERM INT
  kill -TERM "${agent_pid:-}" "${worker_pid:-}" 2>/dev/null || true
  wait
}
trap term TERM INT

# See api.Dockerfile for why this is 0.0.0.0 and not `::`.
echo "[entrypoint] starting agent on :${PORT:-8001}"
/app/.venv/bin/uvicorn dcode_agent.main:app \
  --host "${HOST:-0.0.0.0}" --port "${PORT:-8001}" &
agent_pid=$!

echo "[entrypoint] starting index worker"
/app/.venv/bin/python -m dcode_worker.main &
worker_pid=$!

# `wait -n` returns as soon as EITHER child exits. Waiting on both in sequence
# would leave a container that looks healthy while indexing is silently dead:
# the agent would keep answering, and every submitted repository would sit in
# `queued` forever with nothing to explain it. Exiting takes the platform's
# restart with it, which is the visible failure.
set +e
wait -n
exit_code=$?
set -e

echo "[entrypoint] a child exited with ${exit_code}; stopping the other" >&2
kill -TERM "$agent_pid" "$worker_pid" 2>/dev/null || true
wait 2>/dev/null || true
exit "${exit_code}"
