"""Media upload helper service with thumbnail generation and validation."""

import io
import os
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import UploadFile, HTTPException
from PIL import Image
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import MediaLibrary
from config import config

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml", "image/x-icon"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico"}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB
THUMBNAIL_SIZE = (300, 300)
UPLOAD_DIR = Path(config.UPLOAD_FOLDER)
THUMBNAIL_DIR = UPLOAD_DIR / "thumbnails"

FOLDER_MAP = {
    "products": "products",
    "categories": "categories",
    "brands": "brands",
    "banners": "banners",
    "homepage": "homepage",
    "promotions": "promotions",
    "users": "users",
    "site": "site",
    "blog": "blog",
    "uploads": "uploads",
}


def _validate_filename(filename: str) -> str:
    """Extract and validate file extension, blocking dangerous files."""
    ext = Path(filename or "upload").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' is not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return ext


def _get_image_dimensions(data: bytes) -> tuple[Optional[int], Optional[int]]:
    """Get width and height from image bytes."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            return img.size
    except Exception:
        return None, None


def _create_thumbnail(data: bytes, max_size: tuple[int, int] = THUMBNAIL_SIZE) -> Optional[bytes]:
    """Create a thumbnail from image bytes."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.thumbnail(max_size, Image.LANCZOS)
            buf = io.BytesIO()
            fmt = img.format or "PNG"
            if fmt.upper() == "JPEG":
                img = img.convert("RGB")
            img.save(buf, format=fmt, quality=85)
            return buf.getvalue()
    except Exception:
        return None


async def save_upload(
    file: UploadFile,
    db: AsyncSession,
    *,
    folder: str = "uploads",
    media_type: str = "image",
    uploaded_by: Optional[int] = None,
    alt_text: Optional[str] = None,
) -> MediaLibrary:
    """Validate, save, generate thumbnail, and register an uploaded file.

    Returns the created ``MediaLibrary`` row.
    """
    ext = _validate_filename(file.filename or "upload.jpg")
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' is not allowed. "
                   f"Accepted: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds the maximum size of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    unique_name = f"{uuid.uuid4().hex}{ext}"
    storage_folder = FOLDER_MAP.get(folder, "uploads")
    dest_dir = UPLOAD_DIR / storage_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / unique_name

    async with aiofiles.open(dest, "wb") as f:
        await f.write(contents)

    relative_url = f"/static/images/uploads/{storage_folder}/{unique_name}"

    width, height = _get_image_dimensions(contents)

    thumbnail_url = None
    thumb_data = _create_thumbnail(contents)
    if thumb_data:
        THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        thumb_name = f"thumb_{unique_name}"
        thumb_dest = THUMBNAIL_DIR / thumb_name
        async with aiofiles.open(thumb_dest, "wb") as f:
            await f.write(thumb_data)
        thumbnail_url = f"/static/images/uploads/thumbnails/{thumb_name}"

    media = MediaLibrary(
        filename=unique_name,
        original_filename=file.filename or unique_name,
        file_type=file.content_type or f"image/{ext.lstrip('.')}",
        file_size=len(contents),
        width=width,
        height=height,
        url=relative_url,
        thumbnail_url=thumbnail_url,
        alt_text=alt_text or Path(file.filename or "").stem,
        media_type=media_type,
        folder=storage_folder,
        uploaded_by=uploaded_by,
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)
    return media


async def delete_media_file(media: MediaLibrary) -> None:
    """Delete the physical file and thumbnail for a media entry."""
    base = Path("app/static/images/uploads")
    filepath = base / media.filename
    if filepath.exists():
        os.remove(filepath)
    if media.thumbnail_url:
        thumb_path = base / "thumbnails" / Path(media.thumbnail_url).name
        if thumb_path.exists():
            os.remove(thumb_path)


async def find_media_usage(db: AsyncSession, media_url: str) -> list[dict]:
    """Find all entities using a given image URL."""
    usage = []
    from app.models.catalog import (
        Product, ProductImage, Category, Brand, HeroBanner, BlogPost, User,
    )

    products = (await db.execute(
        select(Product).where(Product.id.in_(
            select(ProductImage.product_id).where(ProductImage.image_url == media_url)
        ))
    )).scalars().all()
    for p in products:
        usage.append({"type": "Product", "id": p.id, "name": p.name})

    cats = (await db.execute(
        select(Category).where(Category.image_url == media_url)
    )).scalars().all()
    for c in cats:
        usage.append({"type": "Category", "id": c.id, "name": c.name})

    brands = (await db.execute(
        select(Brand).where(Brand.image_url == media_url)
    )).scalars().all()
    for b in brands:
        usage.append({"type": "Brand", "id": b.id, "name": b.name})

    banners = (await db.execute(
        select(HeroBanner).where(
            (HeroBanner.image_url == media_url) |
            (HeroBanner.desktop_image_url == media_url) |
            (HeroBanner.tablet_image_url == media_url) |
            (HeroBanner.mobile_image_url == media_url)
        )
    )).scalars().all()
    for b in banners:
        usage.append({"type": "HeroBanner", "id": b.id, "name": b.title})

    blog_posts = (await db.execute(
        select(BlogPost).where(BlogPost.image_url == media_url)
    )).scalars().all()
    for bp in blog_posts:
        usage.append({"type": "BlogPost", "id": bp.id, "name": bp.title})

    users = (await db.execute(
        select(User).where(User.avatar_url == media_url)
    )).scalars().all()
    for u in users:
        usage.append({"type": "User", "id": u.id, "name": u.username})

    return usage


async def count_total_media(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(MediaLibrary))
    return result.scalar_one()


async def count_total_size(db: AsyncSession) -> int:
    result = await db.execute(select(func.coalesce(func.sum(MediaLibrary.file_size), 0)))
    return result.scalar_one()
