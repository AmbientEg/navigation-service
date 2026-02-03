import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from dotenv import load_dotenv

from alembic import context

# Load environment variables
load_dotenv()

# Get Alembic config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models for autogenerate support
from models import Base
target_metadata = Base.metadata

# Get database URL from environment
database_url = os.getenv("DATABASE_URL")

# Convert to asyncpg if needed
if database_url:
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    
    if not url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with an active database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' async mode.
    
    In this scenario we need to create an Engine and associate
    a connection with the context.
    """
    
    # Create async engine
    configuration = {
        "sqlalchemy.url": config.get_main_option("sqlalchemy.url"),
        "sqlalchemy.poolclass": pool.NullPool,
        "sqlalchemy.echo": False,
    }
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        echo=False,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run the migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


# Determine if running in offline mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
