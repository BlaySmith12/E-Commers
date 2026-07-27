"""Extended auth endpoints: forgot-password, reset-password, admin role check."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import User, Permission
from app.schemas import Token, UserOut
from app.security import (
    create_access_token,
    get_current_active_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix='/auth', tags=['Auth Extensions'])

# In-memory reset tokens (production would use DB or email service)
_reset_tokens: dict[str, dict] = {}


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


@router.post('/forgot-password')
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Send password reset link. Always returns success to prevent email enumeration."""
    user = await db.execute(select(User).where(User.email == payload.email))
    user = user.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(48)
        _reset_tokens[token] = {
            'user_id': user.id,
            'expires': datetime.now(timezone.utc) + timedelta(hours=1),
        }
        # Send password reset email (fire-and-forget)
        try:
            from app.services.email_service import send_password_reset_email
            async with async_session_maker() as email_db:
                await send_password_reset_email(email_db, user, token)
                await email_db.commit()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Failed to send password reset email")

    return {"detail": "If an account with that email exists, a reset link has been sent."}


@router.post('/reset-password')
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using token."""
    token_data = _reset_tokens.get(payload.token)
    if not token_data:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if datetime.now(timezone.utc) > token_data['expires']:
        del _reset_tokens[payload.token]
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user = await db.execute(select(User).where(User.id == token_data['user_id']))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.password_hash = hash_password(payload.password)
    await db.commit()

    del _reset_tokens[payload.token]
    return {"detail": "Password reset successfully"}


@router.get('/me', response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_active_user)):
    """Return current user with role info for admin verification."""
    return UserOut.model_validate(current_user)
