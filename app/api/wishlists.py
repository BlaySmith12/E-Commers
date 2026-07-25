"""Wishlist REST API."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.catalog import Wishlist, Product, ProductImage
from app.schemas import MessageOut
from app.security import CurrentUser

router = APIRouter(prefix='/wishlists', tags=['Wishlists'])


def _product_image_url(product: Product) -> str | None:
    if product.images:
        primary = next((i for i in product.images if i.is_primary), None)
        if primary:
            return primary.image_url
        return product.images[0].image_url
    return None


class WishlistItemIn(BaseModel):
    product_id: int


def _serialize_wishlist_item(item: Wishlist) -> dict:
    p = item.product
    return {
        "id": item.id,
        "product_id": item.product_id,
        "created_at": str(item.created_at) if item.created_at else None,
        "product": {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "price": p.price,
            "discount_price": p.discount_price,
            "image_url": _product_image_url(p),
        },
    }


_WISHLIST_LOADING = (
    selectinload(Wishlist.product)
    .selectinload(Product.images)
)


@router.get('')
async def list_wishlist(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Wishlist)
        .where(Wishlist.user_id == current_user.id)
        .options(_WISHLIST_LOADING)
        .order_by(Wishlist.created_at.desc())
    )
    items = result.scalars().unique().all()
    return [_serialize_wishlist_item(i) for i in items]


@router.post('', status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    payload: WishlistItemIn,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    product = (await db.execute(
        select(Product).where(Product.id == payload.product_id).options(selectinload(Product.images))
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    existing = (
        await db.execute(
            select(Wishlist).where(
                Wishlist.user_id == current_user.id,
                Wishlist.product_id == payload.product_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail='Product already in wishlist')

    item = Wishlist(user_id=current_user.id, product_id=payload.product_id)
    db.add(item)
    await db.commit()

    item = (await db.execute(
        select(Wishlist).where(Wishlist.id == item.id).options(_WISHLIST_LOADING)
    )).scalar_one()
    return _serialize_wishlist_item(item)


@router.delete('/{product_id}', response_model=MessageOut)
async def remove_from_wishlist(
    product_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.product_id == product_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail='Item not in wishlist')
    await db.delete(item)
    await db.commit()
    return MessageOut(detail='Item removed from wishlist')
