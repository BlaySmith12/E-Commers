import asyncio, os, sys
os.environ["USE_SQLITE"] = "1"
sys.path.insert(0, ".")

async def main():
    from app.db import async_session_maker
    from sqlalchemy import select
    from app.models.catalog import HeroBanner

    async with async_session_maker() as db:
        result = await db.execute(
            select(HeroBanner)
            .where(HeroBanner.is_active == True)
            .order_by(HeroBanner.position, HeroBanner.created_at.desc())
        )
        banners = result.scalars().all()
        print(f"Found {len(banners)} banners")
        for b in banners:
            data = {"id": b.id, "title": b.title, "subtitle": b.subtitle or "", "image_url": b.image_url or "", "link_url": b.link_url or "/shop", "button_text": b.button_text or "Shop Now"}
            print(data)

asyncio.run(main())
