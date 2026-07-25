#!/bin/sh
set -e

echo "==> Entrypoint starting..."

# ─── Wait for PostgreSQL ──────────────────────────────────────────────────────
echo "Waiting for PostgreSQL..."
until python -c "
import asyncio, os
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

async def check():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect() as conn:
        await conn.execute(sqlalchemy.text('SELECT 1'))
    await engine.dispose()

asyncio.run(check())
" 2>/dev/null; do
  echo "  PostgreSQL not ready yet, retrying in 2s..."
  sleep 2
done
echo "PostgreSQL is ready."

# ─── Run Alembic migrations ───────────────────────────────────────────────────
echo "Running database migrations..."
alembic -c migrations/alembic.ini upgrade head
echo "Migrations complete."

# ─── Seed initial data (roles, admin user) ────────────────────────────────────
echo "Seeding initial data..."
python -c "
import asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import config as settings
from app.models import Role, User

async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Seed roles
        for name, perms in [('Customer', 0), ('Admin', 31)]:
            result = await session.execute(select(Role).where(Role.name == name))
            if not result.scalar_one_or_none():
                session.add(Role(name=name, permissions=perms, default=(name == 'Customer')))
                print(f'  Created role: {name}')

        await session.commit()

        # Seed admin user (only if none exists with Admin role)
        admin_role = (await session.execute(select(Role).where(Role.name == 'Admin'))).scalar_one_or_none()
        if admin_role:
            existing = (await session.execute(
                select(User).where(User.role_id == admin_role.id)
            )).scalar_one_or_none()
            if not existing:
                admin = User(
                    email='admin@primenest.com',
                    username='admin',
                    first_name='Admin',
                    last_name='User',
                    password='admin123',
                    is_active=True,
                    role=admin_role,
                )
                session.add(admin)
                await session.commit()
                print('  Created admin user: admin@primenest.com / admin123')
            else:
                print('  Admin user already exists, skipping.')

    await engine.dispose()

asyncio.run(seed())
"
echo "Seeding complete."

# ─── Start application ────────────────────────────────────────────────────────
echo "==> Starting uvicorn..."
exec uvicorn manage:app --host 0.0.0.0 --port 8000 --workers 2
