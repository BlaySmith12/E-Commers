"""Notification helper service."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Notification


async def create_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str,
    type: str = "info",
) -> Notification:
    """Create and persist a notification for a user."""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        created_at=datetime.utcnow(),
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
) -> list[Notification]:
    """Return notifications for a user, optionally filtered to unread."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    result = await db.execute(stmt)
    return result.scalars().all()


async def mark_read(db: AsyncSession, notification_id: int, user_id: int) -> bool:
    """Mark a single notification as read. Returns True if updated."""
    stmt = (
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    """Mark all of a user's notifications as read. Returns count updated."""
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
