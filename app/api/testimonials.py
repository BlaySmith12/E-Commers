"""Testimonial REST API."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Testimonial
from app.schemas import MessageOut
from app.security import AdminUser
from app.audit import log_audit

router = APIRouter(prefix='/testimonials', tags=['Testimonials'])


class TestimonialCreate(BaseModel):
    customer_name: str
    customer_title: Optional[str] = None
    content: str
    rating: int = 5
    is_featured: bool = False
    is_active: bool = True


class TestimonialUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_title: Optional[str] = None
    content: Optional[str] = None
    rating: Optional[int] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None


class TestimonialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_name: str
    customer_title: Optional[str] = None
    content: str
    rating: int
    is_featured: bool
    is_active: bool
    created_at: Optional[datetime] = None


# ----------------------------- Public -----------------------------
@router.get('', response_model=List[TestimonialOut])
async def list_testimonials(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(Testimonial)
        .where(Testimonial.is_active == True)  # noqa: E712
        .order_by(Testimonial.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ----------------------------- Admin CRUD -----------------------------
@router.post('', response_model=TestimonialOut, status_code=status.HTTP_201_CREATED)
async def create_testimonial(
    payload: TestimonialCreate, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    testimonial = Testimonial(**payload.model_dump())
    db.add(testimonial)
    await db.commit()
    await db.refresh(testimonial)
    await log_audit(
        db=db, action="CREATE", entity_type="Testimonial", entity_id=testimonial.id,
        user_id=admin.id, details=f"Created testimonial by {testimonial.customer_name}"
    )
    return testimonial


@router.put('/{testimonial_id}', response_model=TestimonialOut)
async def update_testimonial(
    testimonial_id: int, payload: TestimonialUpdate,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(Testimonial).where(Testimonial.id == testimonial_id))
    testimonial = result.scalar_one_or_none()
    if not testimonial:
        raise HTTPException(status_code=404, detail='Testimonial not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(testimonial, field, value)
    await db.commit()
    await db.refresh(testimonial)
    await log_audit(
        db=db, action="UPDATE", entity_type="Testimonial", entity_id=testimonial.id,
        user_id=admin.id, details=f"Updated testimonial: {testimonial.customer_name}"
    )
    return testimonial


@router.delete('/{testimonial_id}', response_model=MessageOut)
async def delete_testimonial(
    testimonial_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    result = await db.execute(select(Testimonial).where(Testimonial.id == testimonial_id))
    testimonial = result.scalar_one_or_none()
    if not testimonial:
        raise HTTPException(status_code=404, detail='Testimonial not found')
    customer = testimonial.customer_name
    await db.delete(testimonial)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="Testimonial", entity_id=testimonial_id,
        user_id=admin.id, details=f"Deleted testimonial by {customer}"
    )
    return MessageOut(detail='Testimonial deleted')
