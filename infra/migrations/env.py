"""Alembic environment for Dcode.

Uses `dcode_shared.db.models.Base.metadata` as the autogenerate source so
DESIGN.md §3.2 stays the single source of truth.

The DB URL is read from `shared_settings.database_url` (env-driven) and
the `+asyncpg` driver suffix is stripped because Alembic runs synchronously
(`psycopg2-binary` is the default sync driver, declared in apps/api).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from dcode_shared.db.models import Base
from dcode_shared.settings import shared_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    shared_settings.database_url.replace("+asyncpg", ""),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
