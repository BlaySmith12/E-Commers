"""Audit log REST API."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import AuditLog, SystemLog, User
from app.security import AdminUser

router = APIRouter(prefix='/audit', tags=['Audit'])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[dict] = None


class AuditUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str


class AuditLogDetailOut(AuditLogOut):
    user: Optional[AuditUserOut] = None


class SystemLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    level: str
    message: str
    source: Optional[str] = None
    details: Optional[dict] = None
    created_at: Optional[dict] = None


@router.get('', response_model=List[AuditLogDetailOut])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(AuditLog)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action.upper())
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/system', response_model=List[SystemLogOut])
async def list_system_logs(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    level: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(SystemLog)
    if level is not None:
        stmt = stmt.where(SystemLog.level == level.upper())
    if source is not None:
        stmt = stmt.where(SystemLog.source == source)
    stmt = stmt.order_by(SystemLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
