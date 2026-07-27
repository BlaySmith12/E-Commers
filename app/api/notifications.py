"""Notification REST API."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Notification
from app.schemas import MessageOut
from app.security import CurrentUser, AdminUser

router = APIRouter(prefix='/notifications', tags=['Notifications'])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    message: Optional[str] = None
    type: str
    is_read: bool
    created_at: Optional[datetime] = None


class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: Optional[str] = None
    type: str = 'info'


# ----------------------------- Endpoints -----------------------------
@router.get('', response_model=List[NotificationOut])
async def list_notifications(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    stmt = stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/unread-count')
async def unread_count(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    count = (await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )).scalar_one()
    return {'count': count}


@router.get('/count')
async def notification_count(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id
        )
    )).scalar_one()
    unread = (await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )).scalar_one()
    return {'total': total, 'unread': unread}


@router.post('', response_model=NotificationOut, status_code=201)
async def create_notification(
    data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    notif = Notification(**data.model_dump())
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif


@router.patch('/{notification_id}/read', response_model=NotificationOut)
async def mark_as_read(
    notification_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail='Notification not found')
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


@router.delete('/{notification_id}', response_model=MessageOut)
async def delete_notification(
    notification_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail='Notification not found')
    await db.delete(notification)
    await db.commit()
    return MessageOut(detail='Notification deleted')


@router.patch('/read-all', response_model=MessageOut)
async def mark_all_read(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()
    return MessageOut(detail='All notifications marked as read')
