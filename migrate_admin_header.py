"""Migration: Add User profile fields, Messages table, Login Sessions table."""
import asyncio
from sqlalchemy import text
from app.db import engine

MIGRATION_SQL = [
    # User model additions
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(45)",

    # Messages table
    """CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        sender_name VARCHAR(200) NOT NULL,
        sender_email VARCHAR(256),
        subject VARCHAR(300) NOT NULL,
        body TEXT NOT NULL,
        category VARCHAR(50) DEFAULT 'general',
        is_read BOOLEAN DEFAULT FALSE,
        recipient_id INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT NOW()
    )""",

    # Login Sessions table
    """CREATE TABLE IF NOT EXISTS login_sessions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        ip_address VARCHAR(45),
        user_agent VARCHAR(500),
        browser VARCHAR(100),
        os VARCHAR(100),
        device VARCHAR(100),
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        last_active TIMESTAMP DEFAULT NOW()
    )""",
]

async def migrate():
    async with engine.begin() as conn:
        for stmt in MIGRATION_SQL:
            await conn.execute(text(stmt))
            print(f"OK: {stmt[:70]}...")
    print("\nMigration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
