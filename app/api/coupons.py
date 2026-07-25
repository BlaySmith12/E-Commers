"""Coupon REST API."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Coupon
from app.schemas import MessageOut
from app.security import AdminUser
from app.audit import log_audit

router = APIRouter(prefix='/coupons', tags=['Coupons'])


class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str = 'percentage'
    discount_value: float
    min_order_amount: float = 0.0
    max_uses: int = 0
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class CouponUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    min_order_amount: Optional[float] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    min_order_amount: float
    max_uses: int
    used_count: int
    is_active: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


class CouponValidateIn(BaseModel):
    code: str
    cart_total: float


# ----------------------------- Public -----------------------------
@router.get('/available', response_model=List[CouponOut])
async def list_available_coupons(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(Coupon)
        .where(Coupon.is_active == True)  # noqa: E712
        .order_by(Coupon.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ----------------------------- Admin CRUD -----------------------------
@router.get('', response_model=List[CouponOut])
async def list_coupons(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = select(Coupon).order_by(Coupon.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/{coupon_id}', response_model=CouponOut)
async def get_coupon(coupon_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail='Coupon not found')
    return coupon


@router.post('', response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    payload: CouponCreate, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    dup = await db.execute(select(Coupon).where(Coupon.code == payload.code))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Coupon code already exists')
    coupon = Coupon(**payload.model_dump())
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    await log_audit(
        db=db, action="CREATE", entity_type="Coupon", entity_id=coupon.id,
        user_id=admin.id, details=f"Created coupon: {coupon.code}"
    )
    return coupon


@router.put('/{coupon_id}', response_model=CouponOut)
async def update_coupon(
    coupon_id: int, payload: CouponUpdate,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail='Coupon not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)
    await db.commit()
    await db.refresh(coupon)
    await log_audit(
        db=db, action="UPDATE", entity_type="Coupon", entity_id=coupon.id,
        user_id=admin.id, details=f"Updated coupon: {coupon.code}"
    )
    return coupon


@router.delete('/{coupon_id}', response_model=MessageOut)
async def delete_coupon(
    coupon_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail='Coupon not found')
    coupon_code = coupon.code
    await db.delete(coupon)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="Coupon", entity_id=coupon_id,
        user_id=admin.id, details=f"Deleted coupon: {coupon_code}"
    )
    return MessageOut(detail='Coupon deleted')


# ----------------------------- Public validate -----------------------------
@router.post('/validate', response_model=dict)
async def validate_coupon(payload: CouponValidateIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Coupon).where(Coupon.code == payload.code, Coupon.is_active == True)  # noqa: E712
    )
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail='Invalid coupon code')

    now = datetime.utcnow()
    if coupon.start_date and now < coupon.start_date:
        raise HTTPException(status_code=400, detail='Coupon is not yet active')
    if coupon.end_date and now > coupon.end_date:
        raise HTTPException(status_code=400, detail='Coupon has expired')
    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=400, detail='Coupon usage limit reached')
    if payload.cart_total < coupon.min_order_amount:
        raise HTTPException(
            status_code=400,
            detail=f'Minimum order amount is {coupon.min_order_amount}',
        )

    if coupon.discount_type == 'percentage':
        discount = payload.cart_total * (coupon.discount_value / 100)
    else:
        discount = min(coupon.discount_value, payload.cart_total)

    return {
        'valid': True,
        'discount_type': coupon.discount_type,
        'discount_value': coupon.discount_value,
        'discount_amount': round(discount, 2),
    }
