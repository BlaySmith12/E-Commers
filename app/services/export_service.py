"""Export helper service – generates CSV content via ``io.StringIO``."""

import csv
import io
from datetime import datetime
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Order, OrderItem, Product, User, Role, Permission


def _rows_to_csv(columns: list[str], rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    writer.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
async def export_orders_csv(db: AsyncSession, filters: dict | None = None) -> str:
    """Return CSV string of orders. *filters* may contain:
    ``status``, ``start_date``, ``end_date``.
    """
    stmt = (
        select(Order, User)
        .join(User, Order.user_id == User.id, isouter=True)
        .order_by(Order.created_at.desc())
    )

    filters = filters or {}
    if filters.get("status"):
        stmt = stmt.where(Order.status == filters["status"])
    if filters.get("start_date"):
        stmt = stmt.where(Order.created_at >= filters["start_date"])
    if filters.get("end_date"):
        stmt = stmt.where(Order.created_at <= filters["end_date"])

    result = await db.execute(stmt)
    rows = []
    for row in result.all():
        o = row.Order
        u = row.User
        rows.append([
            o.order_number,
            o.status,
            f"{u.first_name or ''} {u.last_name or ''}".strip() if u else "",
            u.email if u else "",
            f"{o.subtotal:.2f}",
            f"{o.shipping_fee:.2f}",
            f"{o.tax:.2f}",
            f"{o.total_amount:.2f}",
            o.created_at.isoformat() if o.created_at else "",
        ])

    columns = [
        "order_number", "status", "customer_name", "email",
        "subtotal", "shipping_fee", "tax", "total_amount", "created_at",
    ]
    return _rows_to_csv(columns, rows)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
async def export_products_csv(db: AsyncSession, filters: dict | None = None) -> str:
    """Return CSV string of products. *filters* may contain:
    ``category_id``, ``brand_id``, ``status``.
    """
    stmt = select(Product).order_by(Product.name)

    filters = filters or {}
    if filters.get("category_id"):
        stmt = stmt.where(Product.category_id == filters["category_id"])
    if filters.get("brand_id"):
        stmt = stmt.where(Product.brand_id == filters["brand_id"])
    if filters.get("status"):
        stmt = stmt.where(Product.status == filters["status"])

    result = await db.execute(stmt)
    rows = []
    for p in result.scalars().all():
        rows.append([
            p.sku,
            p.name,
            p.category.name if p.category else "",
            p.brand.name if p.brand else "",
            f"{p.price:.2f}",
            f"{p.discount_price:.2f}" if p.discount_price else "",
            p.stock,
            p.status,
            p.created_at.isoformat() if p.created_at else "",
        ])

    columns = [
        "sku", "name", "category", "brand",
        "price", "discount_price", "stock", "status", "created_at",
    ]
    return _rows_to_csv(columns, rows)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
async def export_customers_csv(db: AsyncSession, filters: dict | None = None) -> str:
    """Return CSV string of customers. *filters* may contain:
    ``is_active`` (bool).
    """
    stmt = (
        select(User)
        .where(
            or_(
                User.role_id.is_(None),
                User.role_id.notin_(
                    select(Role.id).where(Role.permissions.op('&')(Permission.ADMIN) > 0).scalar_subquery()
                ),
            )
        )
        .order_by(User.created_at.desc())
    )

    filters = filters or {}
    if filters.get("is_active") is not None:
        stmt = stmt.where(User.is_active == filters["is_active"])

    result = await db.execute(stmt)
    rows = []
    for u in result.scalars().all():
        rows.append([
            u.id,
            u.username,
            u.email,
            f"{u.first_name or ''} {u.last_name or ''}".strip(),
            u.phone or "",
            "Active" if u.is_active else "Inactive",
            u.created_at.isoformat() if u.created_at else "",
        ])

    columns = [
        "id", "username", "email", "full_name",
        "phone", "status", "created_at",
    ]
    return _rows_to_csv(columns, rows)
