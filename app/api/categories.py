"""Category REST API."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Category
from app.schemas import CategoryCreate, CategoryUpdate, CategoryOut, MessageOut
from app.security import AdminUser

router = APIRouter(prefix='/categories', tags=['Categories'])


@router.get('', response_model=List[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db), include_empty: bool = Query(True)):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


@router.get('/{category_id}', response_model=CategoryOut)
async def get_category(category_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    return category


@router.post('', response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    dup = await db.execute(select(Category).where(Category.slug == payload.slug))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Slug already exists')
    category = Category(**payload.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.put('/{category_id}', response_model=CategoryOut)
async def update_category(
    category_id: int, payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)
    return category


@router.delete('/{category_id}', response_model=MessageOut)
async def delete_category(
    category_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    await db.delete(category)
    await db.commit()
    return MessageOut(detail='Category deleted')
