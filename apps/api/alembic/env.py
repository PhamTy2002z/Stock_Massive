"""Alembic environment configuration for async SQLAlchemy."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.core.config import get_settings
from src.core.database import Base

# Import models to register with Base.metadata (bypass stocks __init__.py to avoid vnstock import)
import importlib.util
import sys
from pathlib import Path

models_path = Path(__file__).parent.parent / "src" / "stocks" / "models.py"
spec = importlib.util.spec_from_file_location("models", models_path)
models = importlib.util.module_from_spec(spec)
sys.modules["stocks_models"] = models
spec.loader.exec_module(models)

config = context.config
settings = get_settings()

# Get database URL for migrations
# Prefer direct connection for Supabase (bypasses connection pooler)
def get_migration_url() -> str:
    """Get database URL for migrations."""
    url = settings.database_url_direct or settings.database_url
    # Replace driver prefix
    url = url.replace("postgresql://", "postgresql+asyncpg://")
    # Remove sslmode from URL (asyncpg uses connect_args instead)
    if "?sslmode=" in url:
        url = url.split("?sslmode=")[0]
    elif "&sslmode=" in url:
        url = url.replace("&sslmode=require", "")
    return url

# Set sqlalchemy.url from settings
# Escape % for configparser (% is interpolation character)
database_url = get_migration_url().replace("%", "%%")
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


# SSL config for Supabase connections (asyncpg driver)
def get_connect_args() -> dict:
    """Get SSL connect args for Supabase."""
    url_to_check = settings.database_url_direct or settings.database_url
    if "supabase" in url_to_check.lower():
        return {"ssl": "require"}
    return {}


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=get_connect_args(),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
