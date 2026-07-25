"""Brand REST API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Brand
from app.schemas import BrandCreate, BrandUpdate, BrandOut, MessageOut
from app.security import AdminUser

router = APIRouter(prefix='/brands', tags=['Brands'])


@router.get('', response_model=List[BrandOut])
async def list_brands(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).order_by(Brand.name))
    return result.scalars().all()


@router.get('/{brand_id}', response_model=BrandOut)
async def get_brand(brand_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail='Brand not found')
    return brand


@router.post('', response_model=BrandOut, status_code=status.HTTP_201_CREATED)
async def create_brand(
    payload: BrandCreate, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    dup = await db.execute(select(Brand).where(Brand.slug == payload.slug))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Slug already exists')
    brand = Brand(**payload.model_dump())
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.put('/{brand_id}', response_model=BrandOut)
async def update_brand(
    brand_id: int, payload: BrandUpdate,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail='Brand not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.delete('/{brand_id}', response_model=MessageOut)
async def delete_brand(
    brand_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail='Brand not found')
    await db.delete(brand)
    await db.commit()
    return MessageOut(detail='Brand deleted')
