"""Cart REST API - guest + authenticated user carts."""

from collections import OrderedDict
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Product, ProductImage, Coupon
from app.schemas import CartItemIn, CartItemOut, CartOut, MessageOut
from app.security import CurrentUser, OptionalCurrentUser

router = APIRouter(prefix='/cart', tags=['Cart'])

_cart_store: Dict[str, OrderedDict] = {}
_cart_coupons: Dict[str, str] = {}
CART_SHIPPING_FEE = 15.0
CART_TAX_RATE = 0.15


def _get_cart(cart_id: str) -> OrderedDict:
    return _cart_store.setdefault(cart_id, OrderedDict())


async def _serialize_cart(cart_id: str, db: AsyncSession, coupon_code: str = None) -> CartOut:
    cart = _get_cart(cart_id)
    items: list[CartItemOut] = []
    subtotal = 0.0
    item_count = 0

    for product_id, qty in list(cart.items()):
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product or product.stock < qty:
            cart.pop(product_id, None)
            continue

        unit_price = product.effective_price
        original_price = product.price
        discount_price = product.discount_price
        line_total = unit_price * qty
        subtotal += line_total
        item_count += qty

        img = next((i for i in getattr(product, 'images', []) if i.is_primary), None)
        if not img and product.images:
            img = product.images[0]

        brand_name = None
        if product.brand:
            brand_name = product.brand.name
        category_name = None
        if product.category:
            category_name = product.category.name

        items.append(CartItemOut(
            product_id=product.id,
            name=product.name,
            slug=product.slug,
            quantity=qty,
            unit_price=unit_price,
            original_price=original_price,
            discount_price=discount_price,
            line_total=round(line_total, 2),
            image_url=getattr(img, 'image_url', None) if img else None,
            stock=product.stock,
            sku=product.sku,
            brand=brand_name,
            category=category_name,
        ))

    discount = 0.0
    resolved_coupon = coupon_code
    if coupon_code:
        coupon_result = await db.execute(
            select(Coupon).where(Coupon.code == coupon_code.strip().upper(), Coupon.is_active == True)
        )
        coupon = coupon_result.scalar_one_or_none()
        if coupon:
            from datetime import datetime
            now = datetime.utcnow()
            valid = True
            if coupon.start_date and now < coupon.start_date:
                valid = False
            if coupon.end_date and now > coupon.end_date:
                valid = False
            if coupon.max_uses and coupon.used_count >= coupon.max_uses:
                valid = False
            if subtotal < coupon.min_order_amount:
                valid = False
            if valid:
                if coupon.discount_type == 'percentage':
                    discount = subtotal * (coupon.discount_value / 100)
                else:
                    discount = min(coupon.discount_value, subtotal)
                if coupon.max_discount_amount and coupon.max_discount_amount > 0:
                    discount = min(discount, coupon.max_discount_amount)
            else:
                resolved_coupon = None
        else:
            resolved_coupon = None

    discount = round(discount, 2)
    shipping = CART_SHIPPING_FEE if item_count > 0 else 0.0
    taxable = max(subtotal - discount, 0.0)
    tax = round(taxable * CART_TAX_RATE, 2)
    total = round(taxable + shipping + tax, 2)

    return CartOut(
        items=items,
        subtotal=round(subtotal, 2),
        item_count=item_count,
        discount=discount,
        coupon_code=resolved_coupon,
        shipping_fee=shipping,
        tax=tax,
        total=total,
    )


@router.get('', response_model=CartOut)
async def get_cart(
    cart_id: str = 'default',
    db: AsyncSession = Depends(get_db),
    user: OptionalCurrentUser = None,
):
    if not user:
        return CartOut(items=[], subtotal=0.0, item_count=0, discount=0.0,
                       shipping_fee=0.0, tax=0.0, total=0.0)
    coupon = _cart_coupons.get(cart_id)
    return await _serialize_cart(cart_id, db, coupon)


@router.post('/items', response_model=CartOut)
async def add_item(item: CartItemIn, cart_id: str = 'default', db: AsyncSession = Depends(get_db), user: CurrentUser = None):
    """Requires authentication. Guests cannot add to cart."""
    _ = user
    product = (await db.execute(select(Product).where(Product.id == item.product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    if product.stock < 1:
        raise HTTPException(status_code=400, detail='Out of stock')

    cart = _get_cart(cart_id)
    current = cart.get(item.product_id, 0)
    new_qty = min(current + item.quantity, product.stock)
    cart[item.product_id] = new_qty

    coupon = _cart_coupons.get(cart_id)
    return await _serialize_cart(cart_id, db, coupon)


@router.put('/items/{product_id}', response_model=CartOut)
async def update_item(product_id: int, qty: int, cart_id: str = 'default', db: AsyncSession = Depends(get_db), user: CurrentUser = None):
    _ = user
    if qty < 1:
        raise HTTPException(status_code=400, detail='Quantity must be >= 1')
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    cart = _get_cart(cart_id)
    if product_id not in cart:
        raise HTTPException(status_code=404, detail='Item not in cart')
    cart[product_id] = min(qty, product.stock)

    coupon = _cart_coupons.get(cart_id)
    return await _serialize_cart(cart_id, db, coupon)


@router.delete('/items/{product_id}', response_model=CartOut)
async def remove_item(product_id: int, cart_id: str = 'default', db: AsyncSession = Depends(get_db), user: CurrentUser = None):
    _ = user
    cart = _get_cart(cart_id)
    cart.pop(product_id, None)

    coupon = _cart_coupons.get(cart_id)
    return await _serialize_cart(cart_id, db, coupon)


@router.delete('', response_model=MessageOut)
async def clear_cart(cart_id: str, user: CurrentUser = None):
    _ = user
    _cart_store.pop(cart_id, None)
    _cart_coupons.pop(cart_id, None)
    return MessageOut(detail='Cart cleared')


@router.post('/coupon', response_model=CartOut)
async def apply_coupon(payload: dict, cart_id: str = 'default', db: AsyncSession = Depends(get_db), user: CurrentUser = None):
    _ = user
    code = payload.get('coupon_code', '').strip()
    if not code:
        _cart_coupons.pop(cart_id, None)
    else:
        _cart_coupons[cart_id] = code.upper()
    return await _serialize_cart(cart_id, db, _cart_coupons.get(cart_id))


@router.post('/coupon/remove', response_model=CartOut)
async def remove_coupon(cart_id: str = 'default', db: AsyncSession = Depends(get_db), user: CurrentUser = None):
    _ = user
    _cart_coupons.pop(cart_id, None)
    return await _serialize_cart(cart_id, db, None)
