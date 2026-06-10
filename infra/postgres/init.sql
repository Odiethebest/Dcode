-- Bootstrap SQL run by Postgres on first startup (mounted in docker-compose.yml).
-- Schema tables are created by Alembic migration 001_initial_schema.

CREATE EXTENSION IF NOT EXISTS vector;
