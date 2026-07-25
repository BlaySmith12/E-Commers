"""Search helper service using SQLAlchemy ilike for text search."""

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Product, Order, User


async def search_products(
    db: AsyncSession,
    query: str,
    limit: int = 20,
) -> list[Product]:
    """Search products by name or SKU."""
    term = f"%{query.strip()}%"
    stmt = (
        select(Product)
        .where(or_(Product.name.ilike(term), Product.sku.ilike(term)))
        .order_by(Product.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def search_orders(
    db: AsyncSession,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search orders by order number or customer email."""
    term = f"%{query.strip()}%"
    stmt = (
        select(Order, User)
        .join(User, Order.user_id == User.id, isouter=True)
        .where(or_(Order.order_number.ilike(term), User.email.ilike(term)))
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": row.Order.id,
            "order_number": row.Order.order_number,
            "status": row.Order.status,
            "total_amount": row.Order.total_amount,
            "customer": row.User,
        }
        for row in result.all()
    ]


async def search_customers(
    db: AsyncSession,
    query: str,
    limit: int = 20,
) -> list[User]:
    """Search customers by username, email, or first name."""
    term = f"%{query.strip()}%"
    stmt = (
        select(User)
        .where(
            or_(
                User.username.ilike(term),
                User.email.ilike(term),
                User.first_name.ilike(term),
            )
        )
        .order_by(User.username)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
