"""Create an admin user."""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

from config import config as settings
from app.models.catalog import User, Role
from app.security import hash_password


async def create_admin_user():
    """Create an admin user if one doesn't already exist."""
    # Create async engine
    engine: AsyncEngine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the admin role
        result = await session.execute(select(Role).where(Role.name == "Admin"))
        admin_role = result.scalar_one_or_none()
        
        if not admin_role:
            print("ERROR: Admin role not found. Please run seed_initial.py first.")
            return
        
        # Check if admin user already exists by email or username
        result = await session.execute(select(User).where((User.email == "admin123@example.com") | (User.username == "admin123")))
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            print("Admin user already exists:")
            print(f"  Email: {existing_admin.email}")
            print(f"  Username: {existing_admin.username}")
            print(f"  ID: {existing_admin.id}")
            return
        
        # Create admin user
        admin_user = User(
            email="admin123@example.com",
            username="admin123",
            first_name="Admin",
            last_name="User",
            password="admin123",  # Will be hashed by setter
            role=admin_role,
            is_active=True
        )
        
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        
        print(f"Created admin user: {admin_user.email}")
        print(f"Username: {admin_user.username}")
        print(f"Password: admin123")
        print(f"User ID: {admin_user.id}")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin_user())