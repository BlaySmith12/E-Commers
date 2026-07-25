"""Authentication REST API."""

from fastapi import APIRouter, Depends, HTTPException, status
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
    get_current_active_user,
    get_current_user,
)

router = APIRouter(prefix='/auth', tags=['Authentication'])


@router.post('/register', response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
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

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post('/login', response_model=Token)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    # accept email OR username in `username` field
    user = await db.execute(
        select(User).where(
            (User.email == payload.username) | (User.username == payload.username)
        )
    )
    user = user.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid credentials',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail='Account is inactive')

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get('/me', response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_active_user)):
    return UserOut.model_validate(current_user)


@router.post('/logout', response_model=MessageOut)
async def logout(current_user: User = Depends(get_current_user)):
    # Stateless JWT: client discards the token. Endpoint provided for UX.
    return MessageOut(detail='Logged out successfully')
