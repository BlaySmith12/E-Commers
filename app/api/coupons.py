"""Coupon REST API — admin CRUD + public validate + usage tracking."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Coupon, CouponUsage, User, Order
from app.schemas import MessageOut
from app.security import AdminUser, CurrentUser
from app.audit import log_audit

router = APIRouter(prefix='/coupons', tags=['Coupons'])


# ----------------------------- Schemas -----------------------------
class CouponCreateIn(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str = 'percentage'
    discount_value: float
    min_order_amount: float = 0.0
    max_discount_amount: float = 0.0
    max_uses: int = 0
    max_uses_per_customer: int = 0
    first_order_only: bool = False
    applicable_product_ids: Optional[List[int]] = None
    applicable_category_ids: Optional[List[int]] = None
    applicable_brand_ids: Optional[List[int]] = None
    customer_eligibility: str = 'all'
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class CouponUpdateIn(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    min_order_amount: Optional[float] = None
    max_discount_amount: Optional[float] = None
    max_uses: Optional[int] = None
    max_uses_per_customer: Optional[int] = None
    first_order_only: Optional[bool] = None
    applicable_product_ids: Optional[List[int]] = None
    applicable_category_ids: Optional[List[int]] = None
    applicable_brand_ids: Optional[List[int]] = None
    customer_eligibility: Optional[str] = None
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
    max_discount_amount: float
    max_uses: int
    used_count: int
    max_uses_per_customer: int
    first_order_only: bool
    applicable_product_ids: Optional[list] = None
    applicable_category_ids: Optional[list] = None
    applicable_brand_ids: Optional[list] = None
    customer_eligibility: str
    is_active: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


class CouponUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    coupon_id: int
    user_id: int
    order_id: Optional[int] = None
    discount_amount: float
    used_at: Optional[datetime] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    order_number: Optional[str] = None


class CouponValidateIn(BaseModel):
    code: str
    cart_total: float


class BulkCouponDeleteIn(BaseModel):
    coupon_ids: List[int]


# ----------------------------- Helpers -----------------------------
def _compute_discount(coupon: Coupon, subtotal: float) -> float:
    if coupon.discount_type == 'percentage':
        discount = subtotal * (coupon.discount_value / 100)
    else:
        discount = min(coupon.discount_value, subtotal)
    if coupon.max_discount_amount and coupon.max_discount_amount > 0:
        discount = min(discount, coupon.max_discount_amount)
    return round(discount, 2)


# ----------------------------- Public -----------------------------
@router.get('/available', response_model=List[CouponOut])
async def list_available_coupons(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    now = datetime.utcnow()
    stmt = (
        select(Coupon)
        .where(Coupon.is_active == True)  # noqa: E712
        .where((Coupon.start_date.is_(None)) | (Coupon.start_date <= now))
        .where((Coupon.end_date.is_(None)) | (Coupon.end_date >= now))
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
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    discount_type: Optional[str] = Query(None),
):
    stmt = select(Coupon)
    if search:
        stmt = stmt.where(
            (Coupon.code.ilike(f'%{search}%')) |
            (Coupon.description.ilike(f'%{search}%'))
        )
    if is_active is not None:
        stmt = stmt.where(Coupon.is_active == is_active)
    if discount_type:
        stmt = stmt.where(Coupon.discount_type == discount_type)
    stmt = stmt.order_by(desc(Coupon.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/stats')
async def coupon_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    now = datetime.utcnow()
    total = (await db.execute(select(func.count(Coupon.id)))).scalar() or 0
    active = (await db.execute(
        select(func.count(Coupon.id)).where(Coupon.is_active == True)  # noqa: E712
    )).scalar() or 0
    expired = (await db.execute(
        select(func.count(Coupon.id)).where(Coupon.end_date < now, Coupon.end_date.isnot(None))
    )).scalar() or 0
    total_usage = (await db.execute(select(func.count(CouponUsage.id)))).scalar() or 0
    total_discount = (await db.execute(
        select(func.coalesce(func.sum(CouponUsage.discount_amount), 0))
    )).scalar() or 0
    return {
        'total': total,
        'active': active,
        'expired': expired,
        'total_usage': total_usage,
        'total_discount': round(float(total_discount), 2),
    }


@router.get('/usage', response_model=List[CouponUsageOut])
async def list_coupon_usage(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    coupon_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = (
        select(CouponUsage)
        .outerjoin(User, CouponUsage.user_id == User.id)
        .outerjoin(Order, CouponUsage.order_id == Order.id)
    )
    if coupon_id:
        stmt = stmt.where(CouponUsage.coupon_id == coupon_id)
    if user_id:
        stmt = stmt.where(CouponUsage.user_id == user_id)
    stmt = stmt.order_by(desc(CouponUsage.used_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()
    out = []
    for row in rows:
        cu = row[0]
        user = row[1] if len(row) > 1 else None
        order = row[2] if len(row) > 2 else None
        out.append(CouponUsageOut(
            id=cu.id,
            coupon_id=cu.coupon_id,
            user_id=cu.user_id,
            order_id=cu.order_id,
            discount_amount=cu.discount_amount,
            used_at=cu.used_at,
            customer_name=f'{user.first_name or ""} {user.last_name or ""}'.strip() if user else None,
            customer_email=user.email if user else None,
            order_number=order.order_number if order else None,
        ))
    return out


@router.get('/{coupon_id}', response_model=CouponOut)
async def get_coupon(coupon_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail='Coupon not found')
    return coupon


@router.post('', response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    payload: CouponCreateIn, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    code = payload.code.strip().upper()
    dup = await db.execute(select(Coupon).where(Coupon.code == code))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f'Coupon code "{code}" already exists')
    if payload.discount_type not in ('percentage', 'fixed'):
        raise HTTPException(status_code=400, detail='discount_type must be "percentage" or "fixed"')
    if payload.discount_value <= 0:
        raise HTTPException(status_code=400, detail='discount_value must be positive')
    if payload.discount_type == 'percentage' and payload.discount_value > 100:
        raise HTTPException(status_code=400, detail='Percentage discount cannot exceed 100%')
    if payload.end_date and payload.start_date and payload.end_date <= payload.start_date:
        raise HTTPException(status_code=400, detail='End date must be after start date')

    coupon = Coupon(**payload.model_dump())
    coupon.code = code
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    await log_audit(
        db=db, action="CREATE", entity_type="Coupon", entity_id=coupon.id,
        user_id=admin.id, details=f"Created coupon: {coupon.code} ({coupon.discount_type} {coupon.discount_value})"
    )
    return coupon


@router.put('/{coupon_id}', response_model=CouponOut)
async def update_coupon(
    coupon_id: int, payload: CouponUpdateIn,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail='Coupon not found')

    updates = payload.model_dump(exclude_unset=True)
    if 'code' in updates:
        new_code = updates['code'].strip().upper()
        if new_code != coupon.code:
            dup = await db.execute(select(Coupon).where(Coupon.code == new_code, Coupon.id != coupon_id))
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f'Coupon code "{new_code}" already exists')
        updates['code'] = new_code
    if 'discount_type' in updates and updates['discount_type'] not in ('percentage', 'fixed'):
        raise HTTPException(status_code=400, detail='discount_type must be "percentage" or "fixed"')

    for field, value in updates.items():
        setattr(coupon, field, value)
    coupon.updated_at = datetime.utcnow()
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
    await db.execute(select(CouponUsage).where(CouponUsage.coupon_id == coupon_id))
    await db.delete(coupon)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="Coupon", entity_id=coupon_id,
        user_id=admin.id, details=f"Deleted coupon: {coupon_code}"
    )
    return MessageOut(detail='Coupon deleted')


@router.post('/bulk-delete', response_model=MessageOut)
async def bulk_delete_coupons(
    payload: BulkCouponDeleteIn, db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    if not payload.coupon_ids:
        raise HTTPException(status_code=400, detail='No coupon IDs provided')
    result = await db.execute(select(Coupon).where(Coupon.id.in_(payload.coupon_ids)))
    coupons = result.scalars().all()
    for c in coupons:
        await db.delete(c)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="Coupon", entity_id=0,
        user_id=admin.id, details=f"Deleted {len(coupons)} coupons"
    )
    return MessageOut(detail=f'Deleted {len(coupons)} coupons')


@router.patch('/{coupon_id}/toggle', response_model=CouponOut)
async def toggle_coupon_active(
    coupon_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail='Coupon not found')
    coupon.is_active = not coupon.is_active
    coupon.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(coupon)
    return coupon


# ----------------------------- Public validate -----------------------------
@router.post('/validate', response_model=dict)
async def validate_coupon(
    payload: CouponValidateIn,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
):
    code = payload.code.strip().upper()
    result = await db.execute(
        select(Coupon).where(Coupon.code == code, Coupon.is_active == True)  # noqa: E712
    )
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=400, detail='Invalid coupon code.')

    now = datetime.utcnow()
    if coupon.start_date and now < coupon.start_date:
        raise HTTPException(status_code=400, detail='This coupon is not yet active.')
    if coupon.end_date and now > coupon.end_date:
        raise HTTPException(status_code=400, detail='This coupon has expired.')
    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=400, detail='This coupon has reached its maximum usage limit.')
    if payload.cart_total < coupon.min_order_amount:
        raise HTTPException(
            status_code=400,
            detail=f'This coupon requires a minimum order of GHS {coupon.min_order_amount:.2f}.',
        )

    if current_user and coupon.max_uses_per_customer and coupon.max_uses_per_customer > 0:
        usage_result = await db.execute(
            select(func.count(CouponUsage.id)).where(
                CouponUsage.coupon_id == coupon.id,
                CouponUsage.user_id == current_user.id,
            )
        )
        user_count = usage_result.scalar() or 0
        if user_count >= coupon.max_uses_per_customer:
            raise HTTPException(status_code=400, detail='You have reached the maximum number of uses for this coupon.')

    if current_user and coupon.first_order_only:
        order_count = await db.execute(
            select(func.count(Order.id)).where(
                Order.user_id == current_user.id,
                Order.status.in_(['Paid', 'Processing', 'Shipped', 'Delivered']),
            )
        )
        if (order_count.scalar() or 0) > 0:
            raise HTTPException(status_code=400, detail='This coupon is only valid for your first order.')

    discount = _compute_discount(coupon, payload.cart_total)
    return {
        'valid': True,
        'code': coupon.code,
        'discount_type': coupon.discount_type,
        'discount_value': coupon.discount_value,
        'discount_amount': discount,
        'description': coupon.description,
    }
