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
    from app import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    order_columns = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'Pending'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'GHS'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount FLOAT DEFAULT 0.0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(200)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_email VARCHAR(200)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(30)",
    ]
    address_columns = [
        "ALTER TABLE addresses ADD COLUMN IF NOT EXISTS full_name VARCHAR(200)",
        "ALTER TABLE addresses ADD COLUMN IF NOT EXISTS phone VARCHAR(30)",
    ]
    payment_columns = [
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'paystack'",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS transaction_reference VARCHAR(100)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS paystack_reference VARCHAR(100)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS paystack_access_code VARCHAR(200)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS access_code VARCHAR(200)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS channel VARCHAR(50)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS customer_email VARCHAR(256)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway_response TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid_at TIMESTAMP",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS failure_reason TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'GHS'",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS refund_reference VARCHAR(100)",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS refund_amount FLOAT DEFAULT 0.0",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS refund_reason TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS metadata JSONB",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
    ]
    async with engine.begin() as conn:
        for stmt in order_columns + payment_columns + address_columns:
            await conn.execute(text(stmt))
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
            )
        """))
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE payments ADD CONSTRAINT uq_payments_transaction_reference UNIQUE (transaction_reference);
            EXCEPTION WHEN duplicate_table THEN NULL;
            END $$;
        """))
        # Store visits table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS store_visits (
                id SERIAL PRIMARY KEY,
                visitor_fingerprint VARCHAR(64) NOT NULL,
                page_url VARCHAR(500) NOT NULL,
                referrer VARCHAR(500),
                device_type VARCHAR(20),
                browser VARCHAR(100),
                os VARCHAR(100),
                ip_hash VARCHAR(64),
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                visited_at TIMESTAMP DEFAULT NOW() NOT NULL
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_store_visits_date ON store_visits (visited_at)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_store_visits_fp ON store_visits (visitor_fingerprint, visited_at)"))
        # Activity logs table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY,
                activity_type VARCHAR(50) NOT NULL,
                description TEXT NOT NULL,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                entity_number VARCHAR(100),
                actor_name VARCHAR(200),
                actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                extra_data JSONB,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_activity_logs_created ON activity_logs (created_at)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_activity_logs_type ON activity_logs (activity_type)"))

        # Email logs table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id SERIAL PRIMARY KEY,
                recipient_email VARCHAR(256) NOT NULL,
                recipient_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                email_type VARCHAR(50) NOT NULL,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                subject VARCHAR(300) NOT NULL,
                status VARCHAR(20) DEFAULT 'queued' NOT NULL,
                failure_reason TEXT,
                retry_count INTEGER DEFAULT 0,
                sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_logs_recipient ON email_logs (recipient_email)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_logs_type ON email_logs (email_type)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_logs_status ON email_logs (status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_logs_created ON email_logs (created_at)"))

        # Email preferences table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS email_preferences (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                promotional_emails BOOLEAN DEFAULT TRUE,
                newsletter BOOLEAN DEFAULT TRUE,
                product_promotions BOOLEAN DEFAULT TRUE,
                price_drop_alerts BOOLEAN DEFAULT TRUE,
                back_in_stock_alerts BOOLEAN DEFAULT TRUE,
                review_requests BOOLEAN DEFAULT TRUE,
                loyalty_updates BOOLEAN DEFAULT TRUE,
                coupon_notifications BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        # Customer payment methods table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS customer_payment_methods (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                method_type VARCHAR(50) NOT NULL,
                provider VARCHAR(100),
                account_number VARCHAR(100),
                account_name VARCHAR(200),
                expiry_date VARCHAR(10),
                is_default BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cpm_user ON customer_payment_methods (user_id)"))


async def dispose_engine() -> None:
    await engine.dispose()
