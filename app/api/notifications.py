"""Notification REST API."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Notification, NotificationCampaign, User
from app.schemas import MessageOut
from app.security import CurrentUser, AdminUser
from app.services.email_service import send_broadcast_email

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


class BroadcastCreate(BaseModel):
    title: str
    message: Optional[str] = None
    type: str = 'info'
    category: str = 'promotional'
    audience: str = 'all'  # 'all' | 'specific'
    user_ids: List[int] = []
    send_email: bool = True
    subject: Optional[str] = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    message: Optional[str] = None
    type: str
    category: str
    audience: str
    recipient_count: int
    notifications_created: int
    email_queued: int
    email_skipped: int
    send_email: bool
    created_at: Optional[datetime] = None


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


# ------------------------- Broadcast (admin) -------------------------
_CATEGORY_EMAIL_TYPES = {
    'order_updates': 'broadcast_order',
    'newsletter': 'broadcast_newsletter',
    'promotional': 'broadcast_promotional',
    'product_promotions': 'broadcast_product',
    'price_drop': 'broadcast_price_drop',
    'back_in_stock': 'broadcast_stock',
    'review_request': 'broadcast_review',
    'loyalty': 'broadcast_loyalty',
    'coupon': 'broadcast_coupon',
}


@router.post('/broadcast', response_model=dict, status_code=201)
async def broadcast_notification(
    data: BroadcastCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    if not data.title or not data.title.strip():
        raise HTTPException(status_code=422, detail='Title is required')

    if data.audience == 'specific':
        if not data.user_ids:
            raise HTTPException(status_code=422, detail='Select at least one customer')
        stmt = select(User).where(
            User.id.in_(data.user_ids),
            User.is_admin == False,  # noqa: E712
        )
    else:
        stmt = select(User).where(User.is_admin == False)  # noqa: E712

    recipients = (await db.execute(stmt)).scalars().all()
    if not recipients:
        raise HTTPException(status_code=400, detail='No recipients matched')

    email_type = _CATEGORY_EMAIL_TYPES.get(data.category, 'broadcast_promotional')

    campaign = NotificationCampaign(
        title=data.title.strip(),
        message=data.message,
        type=data.type,
        category=data.category,
        audience=data.audience,
        recipient_count=len(recipients),
        send_email=data.send_email,
        created_by_id=admin.id,
    )
    db.add(campaign)
    await db.flush()

    email_queued = 0
    email_skipped = 0
    for user in recipients:
        db.add(Notification(
            user_id=user.id,
            title=data.title.strip(),
            message=data.message,
            type=data.type,
        ))
        if data.send_email:
            log = await send_broadcast_email(
                db,
                user=user,
                email_type=email_type,
                subject=data.subject,
                title=data.title.strip(),
                message=data.message,
                campaign_id=campaign.id,
            )
            if log is None:
                email_skipped += 1
            else:
                email_queued += 1

    campaign.notifications_created = len(recipients)
    campaign.email_queued = email_queued
    campaign.email_skipped = email_skipped
    await db.commit()
    await db.refresh(campaign)

    from app.audit import log_audit
    await log_audit(
        db=db,
        action='CREATE',
        entity_type='NotificationCampaign',
        entity_id=campaign.id,
        user_id=admin.id,
        details=f"Broadcast '{campaign.title}' to {len(recipients)} customer(s)",
    )
    await db.commit()

    return {
        'id': campaign.id,
        'recipient_count': len(recipients),
        'notifications_created': len(recipients),
        'email_queued': email_queued,
        'email_skipped': email_skipped,
    }


@router.get('/broadcast', response_model=List[CampaignOut])
async def list_broadcasts(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    stmt = (
        select(NotificationCampaign)
        .order_by(NotificationCampaign.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
