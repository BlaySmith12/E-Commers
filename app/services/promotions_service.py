"""Promotions service - auto-applied, code-free promotions.

Promotions differ from coupons: they apply automatically at cart/checkout
based on their rules (storewide, category or product scope) and never
require the customer to enter a code.

Supported promotion types:
  * percent_off   - X% off applicable items (optionally capped)
  * buy_x_get_y   - buy X, get Y free on applicable items
  * spend_save    - spend GHS min_spend, get GHS discount_amount off
  * free_shipping - free shipping when subtotal >= min_spend
"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Promotion


async def get_active_promotions(db: AsyncSession) -> list:
    """Return promotions currently active and within their date window."""
    now = datetime.utcnow()
    result = await db.execute(
        select(Promotion)
        .where(Promotion.is_active == True)  # noqa: E712
        .where((Promotion.start_date.is_(None)) | (Promotion.start_date <= now))
        .where((Promotion.end_date.is_(None)) | (Promotion.end_date >= now))
    )
    return result.scalars().all()


def promo_applies_to(promo: Promotion, product) -> bool:
    """Check whether a promotion applies to a given product."""
    if promo.scope == 'category':
        if not promo.category_id:
            return False
        return product.category_id == promo.category_id
    if promo.scope == 'product':
        if promo.product_id and product.id == promo.product_id:
            return True
        if promo.product_ids and product.id in promo.product_ids:
            return True
        return False
    return True  # storewide


def _base_price(product) -> float:
    return product.effective_price if product.effective_price else product.price


def compute_product_promotion_discount(promo: Promotion, product, qty: int) -> float:
    """Discount a single promotion contributes for one line item."""
    if not promo_applies_to(promo, product):
        return 0.0
    if promo.promotion_type == 'percent_off':
        d = _base_price(product) * qty * (promo.discount_value or 0) / 100
        if promo.max_discount and promo.max_discount > 0:
            d = min(d, promo.max_discount)
        return round(d, 2)
    if promo.promotion_type == 'buy_x_get_y':
        buy = promo.buy_qty or 1
        get = promo.get_qty or 1
        groups = qty // (buy + get)
        return round(groups * get * _base_price(product), 2)
    if promo.promotion_type == 'spend_save':
        return 0.0  # handled at order level
    return 0.0


async def compute_promotion_discount(db: AsyncSession, items, subtotal: float) -> dict:
    """Return the best applicable promotion discount for the whole cart.

    items: iterable of (product, quantity).
    Returns {discount, promotion_id, promotion_name}.
    """
    promos = await get_active_promotions(db)
    best = {'discount': 0.0, 'promotion_id': None, 'promotion_name': None}

    for promo in promos:
        if promo.promotion_type == 'free_shipping':
            continue  # handled separately, does not reduce item subtotal

        d = 0.0
        if promo.promotion_type == 'spend_save':
            if subtotal >= (promo.min_spend or 0):
                d = min(promo.discount_amount or 0, subtotal)
        else:
            for product, qty in items:
                d += compute_product_promotion_discount(promo, product, qty)

        d = round(d, 2)
        if d > best['discount']:
            best = {'discount': d, 'promotion_id': promo.id, 'promotion_name': promo.name}

    return best


async def compute_free_shipping(db: AsyncSession, subtotal: float) -> bool:
    """Return True if an active free-shipping promotion qualifies."""
    promos = await get_active_promotions(db)
    for promo in promos:
        if promo.promotion_type == 'free_shipping' and subtotal >= (promo.min_spend or 0):
            return True
    return False


def product_sale_info(promos: list, product) -> tuple:
    """Compute promo sale price for a product for badges/pricing display.

    Returns (sale_price, pct) or (None, 0) when no percent_off promotion applies.
    """
    best_pct = 0
    for promo in promos:
        if promo.promotion_type != 'percent_off':
            continue
        if promo_applies_to(promo, product) and (promo.discount_value or 0) > best_pct:
            best_pct = promo.discount_value
    if best_pct:
        base = _base_price(product)
        return round(base * (1 - best_pct / 100), 2), best_pct
    return None, 0
