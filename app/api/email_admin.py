"""Admin email management API — logs, settings, test sends, retry."""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, async_session_maker
from app.models.catalog import EmailLog, EmailPreference, User
from app.schemas import MessageOut
from app.security import AdminUser

router = APIRouter(prefix='/email', tags=['Email Admin'])


class EmailLogOut(BaseModel):
    id: int
    recipient_email: str
    email_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    subject: str
    status: str
    failure_reason: Optional[str] = None
    retry_count: int = 0
    sent_at: Optional[str] = None
    created_at: Optional[str] = None


class EmailStatsOut(BaseModel):
    total: int = 0
    sent: int = 0
    failed: int = 0
    queued: int = 0
    sending: int = 0


class TestEmailIn(BaseModel):
    to_email: EmailStr
    email_type: str = "test"


class RetryIn(BaseModel):
    log_ids: List[int]


# --- Logs ---
@router.get('/logs', response_model=List[EmailLogOut])
async def list_email_logs(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    email_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(EmailLog)
    if email_type:
        stmt = stmt.where(EmailLog.email_type == email_type)
    if status:
        stmt = stmt.where(EmailLog.status == status)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(EmailLog.recipient_email.ilike(like) | EmailLog.subject.ilike(like))
    stmt = stmt.order_by(desc(EmailLog.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return [
        EmailLogOut(
            id=log.id,
            recipient_email=log.recipient_email,
            email_type=log.email_type,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            subject=log.subject,
            status=log.status,
            failure_reason=log.failure_reason,
            retry_count=log.retry_count or 0,
            sent_at=log.sent_at.isoformat() if log.sent_at else None,
            created_at=log.created_at.isoformat() if log.created_at else None,
        )
        for log in result.scalars().all()
    ]


@router.get('/stats', response_model=EmailStatsOut)
async def email_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    total = (await db.execute(select(func.count(EmailLog.id)))).scalar() or 0
    sent = (await db.execute(select(func.count(EmailLog.id)).where(EmailLog.status == 'sent'))).scalar() or 0
    failed = (await db.execute(select(func.count(EmailLog.id)).where(EmailLog.status == 'failed'))).scalar() or 0
    queued = (await db.execute(select(func.count(EmailLog.id)).where(EmailLog.status == 'queued'))).scalar() or 0
    sending = (await db.execute(select(func.count(EmailLog.id)).where(EmailLog.status == 'sending'))).scalar() or 0
    return EmailStatsOut(total=total, sent=sent, failed=failed, queued=queued, sending=sending)


@router.post('/test', response_model=MessageOut)
async def send_test_email(
    payload: TestEmailIn,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    from app.services.email_service import send_admin_test_email
    async with async_session_maker() as email_db:
        await send_admin_test_email(email_db, payload.to_email, payload.email_type)
        await email_db.commit()
    return MessageOut(detail=f"Test email queued for {payload.to_email}")


@router.post('/retry', response_model=MessageOut)
async def retry_failed_emails(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    from app.services.email_service import retry_failed_emails
    await retry_failed_emails()
    return MessageOut(detail="Failed emails queued for retry")


@router.get('/preferences/{user_id}')
async def get_user_email_preferences(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(EmailPreference).where(EmailPreference.user_id == user_id))
    pref = result.scalar_one_or_none()
    if not pref:
        return {"user_id": user_id, "all_enabled": True}
    return {
        "user_id": pref.user_id,
        "promotional_emails": pref.promotional_emails,
        "newsletter": pref.newsletter,
        "product_promotions": pref.product_promotions,
        "price_drop_alerts": pref.price_drop_alerts,
        "back_in_stock_alerts": pref.back_in_stock_alerts,
        "review_requests": pref.review_requests,
        "loyalty_updates": pref.loyalty_updates,
        "coupon_notifications": pref.coupon_notifications,
    }
