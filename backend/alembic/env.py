# alembic/env.py

from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

# Import Base and models — but NOT engine creation
from app.database import Base
import app.models  # Ensures all models are registered

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow override via DATABASE_URL env var (for local development)
import os
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Alembic needs sync engine → always use psycopg2 here
    url = config.get_main_option("sqlalchemy.url")
    
    # Ensure it's a sync URL
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()