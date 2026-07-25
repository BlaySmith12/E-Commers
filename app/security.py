"""Security helpers: password hashing, JWT tokens, and FastAPI dependencies."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, Callable

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import User, Role, Permission
from config import config

ALGORITHM = config.JWT_ALGORITHM
SECRET_KEY = config.JWT_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

# Token is sent as:  Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{config.API_PREFIX}/auth/login")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str | int, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {'sub': str(subject), 'exp': expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get('sub')
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
DbSession = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(db: DbSession, token: TokenDep) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail='Inactive user')
    return current_user


def require_permission(permission: int):
    """
    Dependency factory that creates a permission checker for the given permission bit.
    Returns a dependency function that can be used with Depends().
    """
    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        if not current_user.role or not current_user.role.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Permission required: {permission}',
            )
        return current_user
    return permission_checker


# Permission-specific dependencies
RequireViewer = require_permission(Permission.VIEW)
RequireCreator = require_permission(Permission.CREATE)
RequireEditor = require_permission(Permission.EDIT)
RequireDeleter = require_permission(Permission.DELETE)
RequireAdmin = require_permission(Permission.ADMIN)


CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(require_permission(Permission.ADMIN))]
