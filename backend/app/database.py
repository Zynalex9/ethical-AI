# app/database.py

"""
Database connection setup with SQLAlchemy async engine.
Provides async session management and base model class.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# DO NOT create engine here — we'll do it lazily
engine = None
async_session_maker = None


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def create_engine_and_session():
    """Create engine and session maker on first use or app startup."""
    global engine, async_session_maker
    
    if engine is None:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            future=True,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes."""
    create_engine_and_session()  # Ensure engine exists
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables — called on startup."""
    create_engine_and_session()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine on shutdown."""
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None