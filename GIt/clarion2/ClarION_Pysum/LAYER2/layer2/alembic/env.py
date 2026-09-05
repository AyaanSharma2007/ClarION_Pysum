"""
Alembic env.py — reads DATABASE_URL from .env so you never hardcode credentials.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

load_dotenv()

# Alembic Config object
config = context.config

# Override sqlalchemy.url from DATABASE_URL env var (psycopg3 sync driver)
db_url = os.environ.get("DATABASE_URL", "")
# Alembic needs a sync driver — swap asyncpg → psycopg
sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
# Strip asyncpg-specific query parameters that psycopg doesn't understand
if "?" in sync_url:
    base_url, query_string = sync_url.split("?", 1)
    from urllib.parse import parse_qs, urlencode
    params = parse_qs(query_string)
    # Remove asyncpg-only params
    params.pop("prepared_statement_cache_size", None)
    if params:
        sync_url = f"{base_url}?{urlencode(params, doseq=True)}"
    else:
        sync_url = base_url
if sync_url:
    config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic sees the full metadata
import app.models  # noqa: F401, E402
from app.database import Base  # noqa: E402

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
