"""Newsletter subscription REST API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, async_session_maker
from app.models.catalog import NewsletterSubscriber
from app.schemas import MessageOut
from app.security import AdminUser

router = APIRouter(prefix='/newsletters', tags=['Newsletters'])


class SubscribeIn(BaseModel):
    email: EmailStr


class SubscriberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    is_active: bool


# ----------------------------- Public -----------------------------
@router.post('/subscribe', response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def subscribe(payload: SubscribeIn, db: AsyncSession = Depends(get_db)):
    existing = (
        await db.execute(
            select(NewsletterSubscriber).where(NewsletterSubscriber.email == payload.email)
        )
    ).scalar_one_or_none()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail='Email already subscribed')
        existing.is_active = True
        await db.commit()
        return MessageOut(detail='Subscription reactivated')

    sub = NewsletterSubscriber(email=payload.email)
    db.add(sub)
    await db.commit()

    # Send newsletter welcome email (fire-and-forget)
    try:
        from app.services.email_service import send_newsletter_welcome_email
        async with async_session_maker() as email_db:
            await send_newsletter_welcome_email(email_db, payload.email)
            await email_db.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to send newsletter welcome email")

    return MessageOut(detail='Subscribed successfully')


@router.delete('/unsubscribe', response_model=MessageOut)
async def unsubscribe(email: EmailStr, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )
    sub = result.scalar_one_or_none()
    if not sub or not sub.is_active:
        raise HTTPException(status_code=404, detail='Email not found or already unsubscribed')
    sub.is_active = False
    await db.commit()
    return MessageOut(detail='Unsubscribed successfully')


# ----------------------------- Admin -----------------------------
@router.get('', response_model=List[SubscriberOut])
async def list_subscribers(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = (
        select(NewsletterSubscriber)
        .order_by(NewsletterSubscriber.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
