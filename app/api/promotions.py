"""Promotions REST API — auto-applied, code-free store promotions.

Public:  GET /api/promotions        active promotions for storefront display
Admin:   GET/POST /api/promotions/admin, PUT/DELETE /api/promotions/admin/{id}
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Promotion, Product, Category
from app.schemas import MessageOut
from app.security import AdminUser
from app.audit import log_audit

router = APIRouter(prefix='/promotions', tags=['Promotions'])


# ----------------------------- Schemas -----------------------------
class PromotionCreateIn(BaseModel):
    name: str
    description: Optional[str] = None
    promotion_type: str = 'percent_off'  # percent_off, buy_x_get_y, spend_save, free_shipping
    scope: str = 'storewide'  # storewide, category, product
    discount_value: float = 0.0
    discount_amount: float = 0.0
    min_spend: float = 0.0
    buy_qty: int = 0
    get_qty: int = 0
    max_discount: float = 0.0
    product_id: Optional[int] = None
    product_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class PromotionUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    promotion_type: Optional[str] = None
    scope: Optional[str] = None
    discount_value: Optional[float] = None
    discount_amount: Optional[float] = None
    min_spend: Optional[float] = None
    buy_qty: Optional[int] = None
    get_qty: Optional[int] = None
    max_discount: Optional[float] = None
    product_id: Optional[int] = None
    product_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class PromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    promotion_type: str
    scope: str
    discount_value: float
    discount_amount: float
    min_spend: float
    buy_qty: int
    get_qty: int
    max_discount: float
    product_id: Optional[int] = None
    product_ids: Optional[list] = None
    category_id: Optional[int] = None
    is_active: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    product_name: Optional[str] = None
    category_name: Optional[str] = None


async def _serialize(promo: Promotion) -> PromotionOut:
    out = PromotionOut.model_validate(promo)
    if promo.product:
        out.product_name = promo.product.name
    if promo.category:
        out.category_name = promo.category.name
    return out


async def _resolve_scope_ids(payload: PromotionCreateIn | PromotionUpdateIn, promo: Promotion = None):
    if payload.scope == 'product':
        ids = payload.product_ids or []
        if payload.product_id and payload.product_id not in ids:
            ids.append(payload.product_id)
        return {'product_ids': ids or None, 'product_id': ids[0] if ids else None}
    return {'product_ids': None, 'product_id': None}


# ----------------------------- Public -----------------------------
@router.get('', response_model=List[PromotionOut])
async def list_active_promotions(db: AsyncSession = Depends(get_db)):
    from app.services.promotions_service import get_active_promotions
    promos = await get_active_promotions(db)
    return [await _serialize(p) for p in promos]


# ----------------------------- Admin CRUD -----------------------------
@router.get('/admin', response_model=List[PromotionOut])
async def list_promotions(db: AsyncSession = Depends(get_db), admin: AdminUser = None):
    result = await db.execute(select(Promotion).order_by(desc(Promotion.created_at)))
    return [await _serialize(p) for p in result.scalars().all()]


@router.post('/admin', response_model=PromotionOut, status_code=201)
async def create_promotion(
    payload: PromotionCreateIn,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    scope_ids = await _resolve_scope_ids(payload)
    promo = Promotion(
        name=payload.name,
        description=payload.description,
        promotion_type=payload.promotion_type,
        scope=payload.scope,
        discount_value=payload.discount_value,
        discount_amount=payload.discount_amount,
        min_spend=payload.min_spend,
        buy_qty=payload.buy_qty,
        get_qty=payload.get_qty,
        max_discount=payload.max_discount,
        category_id=payload.category_id if payload.scope == 'category' else None,
        product_id=scope_ids['product_id'],
        product_ids=scope_ids['product_ids'],
        is_active=payload.is_active,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(promo)
    await db.flush()
    await log_audit(
        db=db, action="CREATE", entity_type="Promotion", entity_id=promo.id,
        user_id=admin.id,
        details=f"Created promotion: {promo.name} ({promo.promotion_type} {promo.discount_value})",
    )
    await db.commit()
    await db.refresh(promo)
    return await _serialize(promo)


@router.put('/admin/{promo_id}', response_model=PromotionOut)
async def update_promotion(
    promo_id: int,
    payload: PromotionUpdateIn,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(Promotion).where(Promotion.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail='Promotion not found')

    fields = {
        'name', 'description', 'promotion_type', 'scope', 'discount_value',
        'discount_amount', 'min_spend', 'buy_qty', 'get_qty', 'max_discount',
        'category_id', 'is_active', 'start_date', 'end_date',
    }
    data = payload.model_dump(exclude_unset=True)

    new_scope = data.get('scope', promo.scope)
    if new_scope == 'product' or (new_scope == 'product' and data.get('product_ids')):
        ids = data.get('product_ids') or (promo.product_ids or [])
        if data.get('product_id') and data['product_id'] not in ids:
            ids.append(data['product_id'])
        promo.product_ids = ids or None
        promo.product_id = ids[0] if ids else None
    else:
        data.pop('product_ids', None)

    for field, value in data.items():
        if field in fields:
            setattr(promo, field, value)

    if promo.scope != 'product':
        promo.product_id = None
        promo.product_ids = None

    promo.updated_at = datetime.utcnow()
    await db.flush()
    await log_audit(
        db=db, action="UPDATE", entity_type="Promotion", entity_id=promo.id,
        user_id=admin.id, details=f"Updated promotion: {promo.name}",
    )
    await db.commit()
    await db.refresh(promo)
    return await _serialize(promo)


@router.delete('/admin/{promo_id}', response_model=MessageOut)
async def delete_promotion(
    promo_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(Promotion).where(Promotion.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail='Promotion not found')
    name = promo.name
    await db.delete(promo)
    await db.flush()
    await log_audit(
        db=db, action="DELETE", entity_type="Promotion", entity_id=promo_id,
        user_id=admin.id, details=f"Deleted promotion: {name}",
    )
    await db.commit()
    return MessageOut(detail='Promotion deleted')
