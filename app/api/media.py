"""Media Library REST API — upload, list, update, delete, usage tracking."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import MediaLibrary, User
from app.schemas import MessageOut
from app.security import AdminUser, decode_access_token
from app.services.media_service import (
    save_upload, delete_media_file, find_media_usage,
    count_total_media, count_total_size,
)

router = APIRouter(prefix='/media', tags=['Media Library'])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    original_filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    url: str
    thumbnail_url: Optional[str] = None
    alt_text: Optional[str] = None
    media_type: Optional[str] = None
    folder: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MediaUpdate(BaseModel):
    alt_text: Optional[str] = None
    media_type: Optional[str] = None
    folder: Optional[str] = None


class MediaStats(BaseModel):
    total_count: int
    total_size: int
    total_size_formatted: str


# ---------------------------------------------------------------------------
# Public (for storefront if needed)
# ---------------------------------------------------------------------------
@router.get('/public', response_model=List[MediaOut])
async def public_media(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    result = await db.execute(
        select(MediaLibrary).order_by(MediaLibrary.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------------
@router.get('', response_model=List[MediaOut])
async def list_media(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    q: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    folder: Optional[str] = Query(None),
    sort: str = Query('newest'),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(MediaLibrary)
    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            or_(
                MediaLibrary.original_filename.ilike(term),
                MediaLibrary.alt_text.ilike(term),
                MediaLibrary.filename.ilike(term),
            )
        )
    if media_type:
        stmt = stmt.where(MediaLibrary.media_type == media_type)
    if folder:
        stmt = stmt.where(MediaLibrary.folder == folder)

    if sort == 'oldest':
        stmt = stmt.order_by(MediaLibrary.created_at.asc())
    elif sort == 'size':
        stmt = stmt.order_by(MediaLibrary.file_size.desc())
    elif sort == 'name':
        stmt = stmt.order_by(MediaLibrary.original_filename.asc())
    else:
        stmt = stmt.order_by(MediaLibrary.created_at.desc())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/stats', response_model=MediaStats)
async def media_stats(db: AsyncSession = Depends(get_db), admin: AdminUser = None):
    total = await count_total_media(db)
    total_bytes = await count_total_size(db)
    if total_bytes >= 1024 * 1024:
        fmt = f"{total_bytes / (1024 * 1024):.1f} MB"
    elif total_bytes >= 1024:
        fmt = f"{total_bytes / 1024:.1f} KB"
    else:
        fmt = f"{total_bytes} B"
    return MediaStats(total_count=total, total_size=total_bytes, total_size_formatted=fmt)


@router.get('/{media_id}', response_model=MediaOut)
async def get_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(MediaLibrary).where(MediaLibrary.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail='Media not found')
    return media


@router.post('/upload', response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    folder: str = Form('uploads'),
    media_type: str = Form('image'),
    alt_text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    media = await save_upload(
        file, db, folder=folder, media_type=media_type,
        uploaded_by=admin.id, alt_text=alt_text,
    )
    return media


@router.post('/upload-multiple', response_model=List[MediaOut], status_code=status.HTTP_201_CREATED)
async def upload_multiple_media(
    files: List[UploadFile] = File(...),
    folder: str = Form('uploads'),
    media_type: str = Form('image'),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    results = []
    for file in files:
        media = await save_upload(
            file, db, folder=folder, media_type=media_type,
            uploaded_by=admin.id,
        )
        results.append(media)
    return results


@router.put('/{media_id}', response_model=MediaOut)
async def update_media(
    media_id: int,
    payload: MediaUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(MediaLibrary).where(MediaLibrary.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail='Media not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(media, field, value)
    await db.commit()
    await db.refresh(media)
    return media


@router.put('/{media_id}/replace', response_model=MediaOut)
async def replace_media(
    media_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(MediaLibrary).where(MediaLibrary.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail='Media not found')

    old_url = media.url
    new_media = await save_upload(
        file, db, folder=media.folder, media_type=media.media_type,
        uploaded_by=admin.id, alt_text=media.alt_text,
    )

    media.url = new_media.url
    media.thumbnail_url = new_media.thumbnail_url
    media.filename = new_media.filename
    media.original_filename = new_media.original_filename
    media.file_type = new_media.file_type
    media.file_size = new_media.file_size
    media.width = new_media.width
    media.height = new_media.height

    await db.delete(new_media)
    await db.commit()
    await db.refresh(media)

    usage = await find_media_usage(db, old_url)
    for item in usage:
        pass

    return media


@router.get('/{media_id}/usage')
async def get_media_usage(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(MediaLibrary).where(MediaLibrary.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail='Media not found')
    usage = await find_media_usage(db, media.url)
    return {"media_id": media_id, "usage_count": len(usage), "used_by": usage}


@router.delete('/{media_id}', response_model=MessageOut)
async def delete_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    force: bool = Query(False),
):
    result = await db.execute(select(MediaLibrary).where(MediaLibrary.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail='Media not found')

    if not force:
        usage = await find_media_usage(db, media.url)
        if usage:
            names = [f"{u['type']}: {u['name']}" for u in usage[:5]]
            raise HTTPException(
                status_code=409,
                detail=f"This image is being used by {len(usage)} item(s): {', '.join(names)}",
            )

    await delete_media_file(media)
    await db.delete(media)
    await db.commit()
    return MessageOut(detail='Media deleted')


@router.post('/entity-upload', response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_for_entity(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    field: str = Form('image_url'),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    folder_map = {
        "product": "products",
        "category": "categories",
        "brand": "brands",
        "hero_banner": "banners",
        "blog": "blog",
        "user": "users",
        "site": "site",
        "promotion": "promotions",
    }
    folder = folder_map.get(entity_type, "uploads")

    media = await save_upload(
        file, db, folder=folder, media_type=f"entity_{entity_type}",
        uploaded_by=admin.id,
    )

    from app.models.catalog import (
        Product, Category, Brand, HeroBanner, BlogPost, User,
    )

    model_map = {
        "product": (Product, None),
        "category": (Category, None),
        "brand": (Brand, None),
        "hero_banner": (HeroBanner, None),
        "blog": (BlogPost, None),
        "user": (User, None),
    }

    entity_info = model_map.get(entity_type)
    if entity_info:
        model_class = entity_info[0]
        result = await db.execute(select(model_class).where(model_class.id == entity_id))
        entity = result.scalar_one_or_none()
        if entity:
            setattr(entity, field, media.url)
            await db.commit()

    return media
