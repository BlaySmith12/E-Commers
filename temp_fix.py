import asyncio
from sqlalchemy import text
from app.db import engine

async def fix():
    async with engine.begin() as conn:
        result = await conn.execute(text("UPDATE hero_banners SET image_url = REPLACE(image_url, '.jpg', '.png')"))
        print(f"Updated {result.rowcount} rows")
        
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT title, image_url, is_active FROM hero_banners ORDER BY position"))
        for row in r:
            print(f"  {row[0]} | {row[1]} | active={row[2]}")

asyncio.run(fix())
