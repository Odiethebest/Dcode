.PHONY: help up down logs ps check lint typecheck test migrate fmt clean smoke

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
	@echo "  fmt        Auto-format Python + TypeScript"
	@echo "  migrate    Apply Alembic migrations inside the api container"
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
	uv run mypy apps packages
	cd apps/frontend && npm run typecheck

test:
	uv run pytest
	cd apps/frontend && npm test -- --run

check: lint typecheck test

fmt:
	uv run ruff format apps packages
	uv run ruff check --fix apps packages
	cd apps/frontend && npm run fmt

# --- Database ---

migrate:
	docker compose exec api uv run alembic -c infra/migrations/alembic.ini upgrade head

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
