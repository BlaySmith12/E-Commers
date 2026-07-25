"""Hero Banner REST API."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import HeroBanner
from app.schemas import MessageOut
from app.security import AdminUser
from app.audit import log_audit

router = APIRouter(prefix='/hero-banners', tags=['Hero Banners'])


class HeroBannerCreate(BaseModel):
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    desktop_image_url: Optional[str] = None
    tablet_image_url: Optional[str] = None
    mobile_image_url: Optional[str] = None
    link_url: Optional[str] = None
    button_text: Optional[str] = None
    secondary_button_text: Optional[str] = None
    secondary_button_url: Optional[str] = None
    position: int = 0
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    open_new_tab: bool = False


class HeroBannerUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    desktop_image_url: Optional[str] = None
    tablet_image_url: Optional[str] = None
    mobile_image_url: Optional[str] = None
    link_url: Optional[str] = None
    button_text: Optional[str] = None
    secondary_button_text: Optional[str] = None
    secondary_button_url: Optional[str] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    open_new_tab: Optional[bool] = None


class HeroBannerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    desktop_image_url: Optional[str] = None
    tablet_image_url: Optional[str] = None
    mobile_image_url: Optional[str] = None
    link_url: Optional[str] = None
    button_text: Optional[str] = None
    secondary_button_text: Optional[str] = None
    secondary_button_url: Optional[str] = None
    position: int
    is_active: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    open_new_tab: bool = False
    created_at: Optional[datetime] = None


# ----------------------------- Public -----------------------------
@router.get('', response_model=List[HeroBannerOut])
async def list_hero_banners(
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(HeroBanner)
        .where(HeroBanner.is_active == True)  # noqa: E712
        .order_by(HeroBanner.position, HeroBanner.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ----------------------------- Admin CRUD -----------------------------
@router.post('', response_model=HeroBannerOut, status_code=status.HTTP_201_CREATED)
async def create_hero_banner(
    payload: HeroBannerCreate, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    banner = HeroBanner(**payload.model_dump())
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    await log_audit(
        db=db, action="CREATE", entity_type="HeroBanner", entity_id=banner.id,
        user_id=admin.id, details=f"Created hero banner: {banner.title}"
    )
    return banner


@router.put('/{banner_id}', response_model=HeroBannerOut)
async def update_hero_banner(
    banner_id: int, payload: HeroBannerUpdate,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(HeroBanner).where(HeroBanner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail='Hero banner not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(banner, field, value)
    await db.commit()
    await db.refresh(banner)
    await log_audit(
        db=db, action="UPDATE", entity_type="HeroBanner", entity_id=banner.id,
        user_id=admin.id, details=f"Updated hero banner: {banner.title}"
    )
    return banner


@router.delete('/{banner_id}', response_model=MessageOut)
async def delete_hero_banner(
    banner_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    result = await db.execute(select(HeroBanner).where(HeroBanner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail='Hero banner not found')
    title = banner.title
    await db.delete(banner)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="HeroBanner", entity_id=banner_id,
        user_id=admin.id, details=f"Deleted hero banner: {title}"
    )
    return MessageOut(detail='Hero banner deleted')
