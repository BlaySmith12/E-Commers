"""Customer profile and addresses REST API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import User, Address
from app.schemas import (
    UserUpdate,
    AddressCreate,
    AddressUpdate,
    AddressOut,
    MessageOut,
    UserOut,
)
from app.security import CurrentUser

router = APIRouter(prefix='/customers', tags=['Customers'])


@router.get('/me', response_model=UserOut)
async def get_me(current_user: CurrentUser):
    return UserOut.model_validate(current_user)


@router.patch('/me', response_model=UserOut)
async def update_me(
    current_user: CurrentUser,
    payload: UserUpdate, db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return UserOut.model_validate(current_user)


# ------------------------------- Addresses -------------------------------
@router.get('/me/addresses', response_model=List[AddressOut])
async def list_addresses(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Address).where(Address.user_id == current_user.id))
    return result.scalars().all()


@router.post('/me/addresses', response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(
    current_user: CurrentUser,
    payload: AddressCreate, db: AsyncSession = Depends(get_db),
):
    address = Address(**payload.model_dump(), user_id=current_user.id)
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address


@router.put('/me/addresses/{address_id}', response_model=AddressOut)
async def update_address(
    address_id: int, payload: AddressUpdate,
    current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Address).where(Address.id == address_id))
    address = result.scalar_one_or_none()
    if not address or address.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Address not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(address, field, value)
    await db.commit()
    await db.refresh(address)
    return address


@router.delete('/me/addresses/{address_id}', response_model=MessageOut)
async def delete_address(
    address_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Address).where(Address.id == address_id))
    address = result.scalar_one_or_none()
    if not address or address.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Address not found')
    await db.delete(address)
    await db.commit()
    return MessageOut(detail='Address deleted')
