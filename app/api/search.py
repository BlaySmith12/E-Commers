"""Global Admin Search API."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, func, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import (
    Product, Order, User, Category, Brand, Coupon, ProductReview
)
from app.security import AdminUser

router = APIRouter(prefix='/search', tags=['Search'])


class SearchResult(BaseModel):
    type: str
    id: int
    title: str
    subtitle: Optional[str] = None
    image: Optional[str] = None
    url: str


@router.get('', response_model=List[SearchResult])
async def global_search(
    q: str = Query(..., min_length=1),
    admin: AdminUser = None,
    db: AsyncSession = Depends(get_db),
):
    results = []
    pattern = f'%{q}%'

    # Products
    products = (await db.execute(
        select(Product).where(
            or_(Product.name.ilike(pattern), Product.sku.ilike(pattern))
        ).limit(5)
    )).scalars().all()
    for p in products:
        img = None
        if p.images:
            img = p.images[0].image_url
        results.append(SearchResult(
            type='product', id=p.id, title=p.name,
            subtitle=f'SKU: {p.sku}',
            image=img,
            url=f'/admin/products/edit/{p.id}'
        ))

    # Orders
    orders = (await db.execute(
        select(Order).where(
            or_(
                Order.order_number.ilike(pattern),
                Order.id.cast(String).ilike(pattern)
            )
        ).limit(5)
    )).scalars().all()
    for o in orders:
        results.append(SearchResult(
            type='order', id=o.id,
            title=f'#{o.order_number or o.id}',
            subtitle=f'Status: {o.status} | GHS {o.total_amount:.2f}',
            url=f'/admin/orders/edit/{o.id}'
        ))

    # Customers
    customers = (await db.execute(
        select(User).where(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.email.ilike(pattern),
                User.username.ilike(pattern),
            )
        ).limit(5)
    )).scalars().all()
    for c in customers:
        results.append(SearchResult(
            type='customer', id=c.id,
            title=f'{c.first_name or ""} {c.last_name or ""}'.strip() or c.username,
            subtitle=c.email,
            image=c.avatar_url,
            url=f'/admin/customers?highlight={c.id}'
        ))

    # Categories
    categories = (await db.execute(
        select(Category).where(Category.name.ilike(pattern)).limit(3)
    )).scalars().all()
    for c in categories:
        results.append(SearchResult(
            type='category', id=c.id, title=c.name,
            subtitle='Category',
            image=c.image_url,
            url='/admin/categories'
        ))

    # Brands
    brands = (await db.execute(
        select(Brand).where(Brand.name.ilike(pattern)).limit(3)
    )).scalars().all()
    for b in brands:
        results.append(SearchResult(
            type='brand', id=b.id, title=b.name,
            subtitle='Brand',
            image=b.image_url,
            url='/admin/brands'
        ))

    # Coupons
    coupons = (await db.execute(
        select(Coupon).where(
            or_(Coupon.code.ilike(pattern), Coupon.description.ilike(pattern))
        ).limit(3)
    )).scalars().all()
    for c in coupons:
        results.append(SearchResult(
            type='coupon', id=c.id, title=c.code,
            subtitle=c.description or f'{c.discount_value}% off',
            url='/admin/coupons'
        ))

    return results
