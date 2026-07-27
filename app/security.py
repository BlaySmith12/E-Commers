"""Security helpers: password hashing, JWT tokens, brute-force protection, and FastAPI dependencies."""

import secrets
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
import re

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
# Password policy
# ---------------------------------------------------------------------------
_MIN_PASSWORD_LENGTH = 8

_PASSWORD_POLICY_MSG = (
    "Password must be at least 8 characters and contain at least one uppercase letter, "
    "one lowercase letter, and one digit."
)


def validate_password_strength(password: str) -> None:
    """Raise HTTPException 400 if password does not meet strength requirements."""
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=_PASSWORD_POLICY_MSG)
    if not re.search(r'[A-Z]', password):
        raise HTTPException(status_code=400, detail=_PASSWORD_POLICY_MSG)
    if not re.search(r'[a-z]', password):
        raise HTTPException(status_code=400, detail=_PASSWORD_POLICY_MSG)
    if not re.search(r'[0-9]', password):
        raise HTTPException(status_code=400, detail=_PASSWORD_POLICY_MSG)


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
# Brute-force protection (in-memory, per-IP)
# ---------------------------------------------------------------------------
class _BruteForceTracker:
    """Track failed login attempts per IP with progressive lockout.

    After MAX_FAILURES within WINDOW_SECONDS the IP is locked out for
    LOCKOUT_SECONDS.  A successful login clears the counter.
    """

    MAX_FAILURES = 10
    WINDOW_SECONDS = 600  # 10 minutes
    LOCKOUT_SECONDS = 900  # 15 minutes

    def __init__(self):
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}

    def is_locked(self, ip: str) -> bool:
        with self._lock:
            unlock_at = self._lockouts.get(ip, 0)
            if unlock_at and time.monotonic() < unlock_at:
                return True
            if unlock_at and time.monotonic() >= unlock_at:
                del self._lockouts[ip]
                self._failures.pop(ip, None)
            return False

    def record_failure(self, ip: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._failures[ip] = [t for t in self._failures[ip] if now - t < self.WINDOW_SECONDS]
            self._failures[ip].append(now)
            if len(self._failures[ip]) >= self.MAX_FAILURES:
                self._lockouts[ip] = now + self.LOCKOUT_SECONDS
                self._failures.pop(ip, None)

    def clear(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)
            self._lockouts.pop(ip, None)


brute_force = _BruteForceTracker()


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str | int, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        'sub': str(subject),
        'exp': expire,
        'iat': now,
        'jti': secrets.token_hex(16),
    }
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
    """Dependency factory that creates a permission checker for the given permission bit."""
    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        if not current_user.role or not current_user.role.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Insufficient permissions',
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
