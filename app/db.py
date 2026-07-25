import os
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase
from config import config

# Use SQLite for local dev when PostgreSQL is not available
DATABASE_URL = config.DATABASE_URL
if "postgresql" in DATABASE_URL and os.environ.get("USE_SQLITE", "0") == "1":
    DATABASE_URL = "sqlite+aiosqlite:///./app.db"

# Create async engine with connection pooling
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=config.DEBUG,
    pool_pre_ping=True,
    **({"pool_size": 10, "max_overflow": 20, "pool_recycle": 1800} if "postgresql" in DATABASE_URL else {}),
)

# Async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base for all models."""


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (dev convenience). Use migrations in production."""
    # Import all models so they register on Base.metadata
    from app import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    await engine.dispose()
