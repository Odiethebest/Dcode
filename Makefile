.PHONY: help up down logs ps check lint typecheck test migrate requirements fmt clean smoke frontend-build eval-smoke prod-up prod-down prod-migrate prod-smoke

# ============================================================
# Dcode developer commands. See README.md for the 5-minute guide.
# ============================================================

help:
	@echo "Targets:"
	@echo "  up         Bring up all services via docker compose"
	@echo "  down       Tear down services (keeps volumes)"
	@echo "  down-all   Tear down services AND volumes (destructive)"
	@echo "  logs       Tail logs for all services"
	@echo "  ps         List service status"
	@echo "  check      Run lint + typecheck + tests across all packages"
	@echo "  lint       Run ruff (Python) + eslint (TypeScript)"
	@echo "  typecheck  Run mypy --strict + tsc --noEmit"
	@echo "  test       Run pytest + vitest"
	@echo "  frontend-build  Build the frontend production bundle"
	@echo "  eval-smoke Run the offline evaluation harness smoke test"
	@echo "  prod-up    Bring up the production compose overlay"
	@echo "  prod-down  Tear down the production compose overlay"
	@echo "  prod-migrate  Apply migrations inside the production compose overlay"
	@echo "  prod-smoke Hit the public production entrypoint locally"
	@echo "  fmt        Auto-format Python + TypeScript"
	@echo "  migrate    Apply Alembic migrations inside the api container"
	@echo "  requirements  Regenerate requirements{,-dev}.txt pip fallbacks from uv.lock"
	@echo "  smoke      Hit /healthz on every service"
	@echo "  clean      Remove caches and build artifacts"

# --- Docker lifecycle ---

up:
	docker compose up -d --build

down:
	docker compose down

down-all:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# --- Code quality ---

lint:
	uv run ruff check apps packages
	cd apps/frontend && npm run lint

typecheck:
	MYPYPATH=packages/shared/src:apps/api/src:apps/worker/src:apps/agent/src:apps/eval/src uv run mypy -p dcode_shared -p dcode_api -p dcode_worker -p dcode_agent -p dcode_eval
	cd apps/frontend && npm run typecheck

test:
	uv run pytest
	cd apps/frontend && npm test -- --run

check: lint typecheck test

frontend-build:
	cd apps/frontend && npm run build

eval-smoke:
	PYTHONPATH=packages/shared/src:apps/api/src:apps/worker/src:apps/agent/src:apps/eval/src uv run python -m dcode_eval.smoke

prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-migrate:
	docker compose -f docker-compose.prod.yml exec api uv run alembic -c infra/migrations/alembic.ini upgrade head

prod-smoke:
	@echo "Frontend root:" && curl -fsS http://localhost:$${PUBLIC_HTTP_PORT:-80}/ > /dev/null && echo OK
	@echo "Frontend healthz:" && curl -fsS http://localhost:$${PUBLIC_HTTP_PORT:-80}/healthz && echo
	@echo "API proxy:" && curl -fsS -X POST http://localhost:$${PUBLIC_HTTP_PORT:-80}/api/v1/repos -H 'Content-Type: application/json' -d '{"url":"not-a-git-url"}' || true

fmt:
	uv run ruff format apps packages
	uv run ruff check --fix apps packages
	cd apps/frontend && npm run fmt

# --- Database ---

migrate:
	docker compose exec api uv run alembic -c infra/migrations/alembic.ini upgrade head

# --- Pip-fallback requirements files (regenerate from uv.lock) ---

requirements:
	@printf '# ============================================================\n# Dcode runtime dependencies — pip-only fallback.\n#\n# Primary path is `uv sync` from pyproject.toml + uv.lock.\n# This file exists for environments that don'"'"'t run uv.\n#\n# Install:\n#   pip install -r requirements.txt\n#   pip install -e packages/shared -e apps/api -e apps/worker -e apps/agent -e apps/eval\n#\n# Regenerate: make requirements\n# ============================================================\n\n' > requirements.txt
	uv export --format requirements-txt --no-hashes --all-packages --no-emit-workspace --no-dev >> requirements.txt
	@printf '# ============================================================\n# Dcode runtime + dev dependencies — pip-only fallback.\n#\n# Adds ruff / mypy / pytest / pytest-asyncio / httpx on top of\n# requirements.txt. Primary path is `uv sync`.\n#\n# Install:\n#   pip install -r requirements-dev.txt\n#   pip install -e packages/shared -e apps/api -e apps/worker -e apps/agent -e apps/eval\n#\n# Regenerate: make requirements\n# ============================================================\n\n' > requirements-dev.txt
	uv export --format requirements-txt --no-hashes --all-packages --no-emit-workspace >> requirements-dev.txt
	@echo "Regenerated requirements.txt (runtime) and requirements-dev.txt (with dev)"

# --- Smoke tests ---

smoke:
	@echo "API:"      && curl -fsS http://localhost:8000/healthz || echo "FAIL"
	@echo "Agent:"    && curl -fsS http://localhost:8001/healthz || echo "FAIL"
	@echo "Frontend:" && curl -fsS http://localhost:5173        > /dev/null && echo OK || echo "FAIL"

# --- Cleanup ---

clean:
	find . -type d -name __pycache__   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules  -prune -exec rm -rf {} + 2>/dev/null || true
