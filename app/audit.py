"""Audit logging utilities for admin actions."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import AuditLog


async def log_audit(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Create an audit log entry."""
    audit = AuditLog(
        user_id=user_id,
        action=action.upper(),
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
        created_at=datetime.utcnow(),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


async def get_audit_logs(
    db: AsyncSession,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Query audit logs with optional filters."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action.upper())
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
