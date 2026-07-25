"""Admin Profile, Preferences, Security, and Activity Log API."""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import User, AuditLog, LoginSession
from app.security import CurrentUser, hash_password, verify_password

router = APIRouter(prefix='/admin', tags=['Admin Profile'])


# --- Schemas ---
class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    two_factor_enabled: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    role_name: Optional[str] = None


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PreferencesUpdate(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    date_format: Optional[str] = None
    email_notifications: Optional[bool] = None
    order_notifications: Optional[bool] = None
    inventory_alerts: Optional[bool] = None
    customer_notifications: Optional[bool] = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None


class LoginSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ip_address: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None


# --- Profile Endpoints ---
@router.get('/profile', response_model=ProfileOut)
async def get_profile(current_user: CurrentUser):
    return ProfileOut(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
        two_factor_enabled=current_user.two_factor_enabled or False,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        role_name=current_user.role.name if current_user.role else None,
    )


@router.patch('/profile', response_model=ProfileOut)
async def update_profile(
    data: ProfileUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if data.first_name is not None:
        current_user.first_name = data.first_name
    if data.last_name is not None:
        current_user.last_name = data.last_name
    if data.phone is not None:
        current_user.phone = data.phone
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    if data.email is not None and data.email != current_user.email:
        existing = (await db.execute(
            select(User).where(User.email == data.email, User.id != current_user.id)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail='Email already in use')
        current_user.email = data.email
    await db.commit()
    await db.refresh(current_user)
    return ProfileOut(
        id=current_user.id, email=current_user.email,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
        two_factor_enabled=current_user.two_factor_enabled or False,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        role_name=current_user.role.name if current_user.role else None,
    )


@router.post('/change-password')
async def change_password(
    data: PasswordChange,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail='Current password is incorrect')
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail='Password must be at least 6 characters')
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    return {'detail': 'Password changed successfully'}


# --- Preferences ---
@router.get('/preferences')
async def get_preferences(current_user: CurrentUser):
    prefs = current_user.preferences or {}
    return {
        'theme': prefs.get('theme', 'dark'),
        'language': prefs.get('language', 'en'),
        'timezone': prefs.get('timezone', 'Africa/Accra'),
        'currency': prefs.get('currency', 'GHS'),
        'date_format': prefs.get('date_format', 'MMM DD, YYYY'),
        'email_notifications': prefs.get('email_notifications', True),
        'order_notifications': prefs.get('order_notifications', True),
        'inventory_alerts': prefs.get('inventory_alerts', True),
        'customer_notifications': prefs.get('customer_notifications', True),
    }


@router.patch('/preferences')
async def update_preferences(
    data: PreferencesUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    prefs = current_user.preferences or {}
    update_data = data.model_dump(exclude_unset=True)
    prefs.update(update_data)
    current_user.preferences = prefs
    await db.commit()
    return {'detail': 'Preferences saved', 'preferences': prefs}


# --- Security / Sessions ---
@router.get('/sessions', response_model=List[LoginSessionOut])
async def list_sessions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoginSession)
        .where(LoginSession.user_id == current_user.id)
        .order_by(LoginSession.created_at.desc())
        .limit(20)
    )
    return result.scalars().all()


@router.post('/sessions/revoke-all')
async def revoke_all_sessions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import update as sa_update
    stmt = (
        sa_update(LoginSession)
        .where(LoginSession.user_id == current_user.id, LoginSession.is_active == True)
        .values(is_active=False)
    )
    await db.execute(stmt)
    await db.commit()
    return {'detail': 'All other sessions terminated'}


@router.post('/toggle-2fa')
async def toggle_2fa(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    current_user.two_factor_enabled = not current_user.two_factor_enabled
    await db.commit()
    return {'two_factor_enabled': current_user.two_factor_enabled}


# --- Activity Log ---
@router.get('/activity', response_model=List[AuditLogOut])
async def list_activity(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc())
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get('/activity/recent')
async def recent_activity(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    return result.scalars().all()
