import os
from sqlalchemy import text
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
        # Run migrations for existing tables
        await conn.execute(text("""
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'Pending';
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'GHS';
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount FLOAT DEFAULT 0.0;
        """))
        await conn.execute(text("""
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'paystack';
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS transaction_reference VARCHAR(100);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS paystack_reference VARCHAR(100);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS paystack_access_code VARCHAR(200);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS access_code VARCHAR(200);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS channel VARCHAR(50);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS customer_email VARCHAR(256);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway_response TEXT;
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid_at TIMESTAMP;
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS failure_reason TEXT;
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'GHS';
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS refund_reference VARCHAR(100);
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS refund_amount FLOAT DEFAULT 0.0;
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS refund_reason TEXT;
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS metadata JSONB;
            ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;
        """))
    # Create payment_events table if not exists
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS payment_events (
                id SERIAL PRIMARY KEY,
                payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
                event_type VARCHAR(100) NOT NULL,
                event_reference VARCHAR(100),
                gateway_response TEXT,
                payload JSONB,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))
        # Add unique constraint to payments.transaction_reference if not exists
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE payments ADD CONSTRAINT uq_payments_transaction_reference UNIQUE (transaction_reference);
            EXCEPTION WHEN duplicate_table THEN NULL;
            END $$;
        """))


async def dispose_engine() -> None:
    await engine.dispose()
