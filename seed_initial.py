"""Seed the database with required default data (roles, categories, brands)."""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.catalog import Role, Category, Brand
from config import config as settings

ROLES = [
    {'name': 'Customer', 'default': True, 'permissions': 0},
    {'name': 'Admin', 'default': False, 'permissions': 31},
]

CATEGORIES = [
    {'name': 'Electronics', 'slug': 'electronics'},
    {'name': 'Fashion', 'slug': 'fashion'},
    {'name': 'Home & Kitchen', 'slug': 'home-kitchen'},
]

BRANDS = [
    {'name': 'TechPro', 'slug': 'techpro'},
    {'name': 'StyleHub', 'slug': 'stylehub'},
    {'name': 'HomeEssentials', 'slug': 'homeessentials'},
]


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for role_data in ROLES:
            exists = await session.execute(select(Role).where(Role.name == role_data['name']))
            if not exists.scalar_one_or_none():
                session.add(Role(**role_data))

        for cat_data in CATEGORIES:
            exists = await session.execute(select(Category).where(Category.slug == cat_data['slug']))
            if not exists.scalar_one_or_none():
                session.add(Category(**cat_data))

        for brand_data in BRANDS:
            exists = await session.execute(select(Brand).where(Brand.slug == brand_data['slug']))
            if not exists.scalar_one_or_none():
                session.add(Brand(**brand_data))

        await session.commit()

    await engine.dispose()
    print('Seed complete.')


if __name__ == '__main__':
    asyncio.run(main())
