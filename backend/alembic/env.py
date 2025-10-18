from __future__ import annotations

import asyncio
from collections.abc import Iterable
import importlib
import os
import pkgutil
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    def load_dotenv() -> bool:
        return False

# Ensure the project and package roots are importable.
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

for path in {PROJECT_ROOT, BACKEND_DIR}:
    if path and path not in sys.path:
        sys.path.insert(0, path)

# Load environment variables early so DATABASE_URL is available.
load_dotenv()

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

config.set_main_option("sqlalchemy.url", database_url)


def _import_all_models() -> None:
    """Import all modules within backend.models to register SQLModel metadata."""
    import backend.models as models_package  # noqa: F401

    def iter_modules(package) -> Iterable[str]:
        if hasattr(package, "__path__"):
            for module_info in pkgutil.walk_packages(
                package.__path__,
                package.__name__ + ".",
            ):
                yield module_info.name

    for module_name in iter_modules(models_package):
        importlib.import_module(module_name)


_import_all_models()

try:
    model_base = getattr(
        importlib.import_module("backend.models"),
        "SQLModel",
        SQLModel,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback safeguard
    model_base = SQLModel

target_metadata = model_base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode, supporting sync and async engines."""
    if database_url.startswith(
        ("postgresql+asyncpg", "mysql+asyncmy", "sqlite+aiosqlite"),
    ):
        async def async_run() -> None:
            connectable: AsyncEngine = create_async_engine(
                database_url,
                poolclass=pool.NullPool,
            )
            try:
                async with connectable.connect() as connection:
                    await connection.run_sync(do_run_migrations)
            finally:
                await connectable.dispose()

        asyncio.run(async_run())
    else:
        section = config.get_section(config.config_ini_section) or {}
        section["sqlalchemy.url"] = database_url
        connectable = engine_from_config(
            section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()