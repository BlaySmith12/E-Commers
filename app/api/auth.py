"""Authentication REST API."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import User, Role, Permission
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    Token,
    UserOut,
    MessageOut,
)
from app.security import (
    create_access_token,
    hash_password,
    verify_password,
    validate_password_strength,
    brute_force,
    get_current_active_user,
    get_current_user,
)
from app.activity import log_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/auth', tags=['Authentication'])


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.post('/register', response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Enforce password strength
    validate_password_strength(payload.password)

    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail='Passwords do not match')

    # uniqueness checks
    existing_email = await db.execute(select(User).where(User.email == payload.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Email already registered')
    existing_username = await db.execute(select(User).where(User.username == payload.username))
    if existing_username.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Username already taken')

    # assign default role
    role_result = await db.execute(select(Role).where(Role.default == True))  # noqa: E712
    role = role_result.scalars().first()

    user = User(
        username=payload.username,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        password=payload.password,  # triggers hashing via setter
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Log activity
    try:
        await log_activity(
            db=db,
            activity_type="customer_registered",
            description=f"New customer registered: {((user.first_name or '') + ' ' + (user.last_name or '')).strip() or user.email}",
            entity_type="User",
            entity_id=user.id,
            actor_name=((user.first_name or '') + ' ' + (user.last_name or '')).strip() or user.email,
            actor_id=user.id,
        )
        await db.commit()
    except Exception:
        pass

    # Send welcome email (fire-and-forget)
    try:
        from app.services.email_service import send_welcome_email
        await send_welcome_email(db, user)
        await db.commit()
    except Exception:
        pass

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post('/login', response_model=Token)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)

    # Brute-force check
    if brute_force.is_locked(ip):
        logger.warning("Login blocked by brute-force protection from IP %s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Too many failed login attempts. Please try again later.',
        )

    # accept email OR username in `username` field
    user = await db.execute(
        select(User).where(
            (User.email == payload.username) | (User.username == payload.username)
        )
    )
    user = user.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        brute_force.record_failure(ip)
        logger.warning("Failed login attempt from IP %s for user %s", ip, payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid credentials',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail='Account is inactive')

    # Clear brute-force counter on successful login
    brute_force.clear(ip)

    # Remember me → 30 days; otherwise default 60 minutes
    expires = 43200 if payload.remember_me else None
    token = create_access_token(subject=user.id, expires_minutes=expires)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get('/me', response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_active_user)):
    return UserOut.model_validate(current_user)


@router.post('/logout', response_model=MessageOut)
async def logout(current_user: User = Depends(get_current_user)):
    return MessageOut(detail='Logged out successfully')
