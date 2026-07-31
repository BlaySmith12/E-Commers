"""Admin Messages API."""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import Message
from app.security import AdminUser

router = APIRouter(prefix='/messages', tags=['Messages'])


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sender_name: str
    sender_email: Optional[str] = None
    subject: str
    body: str
    category: str
    is_read: bool
    created_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    sender_name: str
    sender_email: Optional[str] = None
    subject: str
    body: str
    category: str = 'general'


@router.get('', response_model=List[MessageOut])
async def list_messages(
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
    unread_only: bool = Query(False),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = select(Message)
    if unread_only:
        stmt = stmt.where(Message.is_read == False)
    if category:
        stmt = stmt.where(Message.category == category)
    stmt = stmt.order_by(Message.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/count')
async def message_count(
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count()).select_from(Message))).scalar_one()
    unread = (await db.execute(
        select(func.count()).select_from(Message).where(Message.is_read == False)
    )).scalar_one()
    return {'total': total, 'unread': unread}


@router.get('/unread-count')
async def unread_count(
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    count = (await db.execute(
        select(func.count()).select_from(Message).where(Message.is_read == False)
    )).scalar_one()
    return {'count': count}


@router.patch('/{message_id}/read')
async def mark_as_read(
    message_id: int,
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail='Message not found')
    msg.is_read = True
    await db.commit()
    await db.refresh(msg)
    return msg


@router.patch('/read-all')
async def mark_all_read(
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    stmt = update(Message).where(Message.is_read == False).values(is_read=True)
    await db.execute(stmt)
    await db.commit()
    return {'detail': 'All messages marked as read'}


@router.delete('/{message_id}')
async def delete_message(
    message_id: int,
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail='Message not found')
    await db.delete(msg)
    await db.commit()
    return {'detail': 'Message deleted'}


@router.post('', response_model=MessageOut, status_code=201)
async def create_message(
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    msg = Message(**data.model_dump())
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Notify admin via SMS (fire-and-forget)
    try:
        import asyncio
        from app.services.sms_service import send_admin_sms_message
        name = data.sender_name or 'Visitor'
        subject = data.subject or 'New message'
        task = asyncio.create_task(
            send_admin_sms_message(f"New contact message | {name} | {subject} | {data.sender_email}")
        )
        from app.activity import _sms_tasks
        _sms_tasks.add(task)
        task.add_done_callback(_sms_tasks.discard)
    except Exception:
        pass

    return msg
