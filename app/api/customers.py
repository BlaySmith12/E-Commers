"""Customer profile, addresses, and payment methods REST API."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import User, Address, CustomerPaymentMethod, EmailPreference
from app.schemas import (
    UserUpdate,
    AddressCreate,
    AddressUpdate,
    AddressOut,
    PaymentMethodCreate,
    PaymentMethodUpdate,
    PaymentMethodOut,
    MessageOut,
    UserOut,
)
from app.security import CurrentUser, verify_password, hash_password
from pydantic import BaseModel

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


# ------------------------------- Payment Methods -------------------------------
@router.get('/me/payment-methods', response_model=List[PaymentMethodOut])
async def list_payment_methods(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CustomerPaymentMethod).where(CustomerPaymentMethod.user_id == current_user.id)
        .order_by(CustomerPaymentMethod.is_default.desc(), CustomerPaymentMethod.created_at.desc())
    )
    return result.scalars().all()


@router.post('/me/payment-methods', response_model=PaymentMethodOut, status_code=status.HTTP_201_CREATED)
async def create_payment_method(
    current_user: CurrentUser,
    payload: PaymentMethodCreate, db: AsyncSession = Depends(get_db),
):
    if payload.is_default:
        result = await db.execute(
            select(CustomerPaymentMethod).where(
                CustomerPaymentMethod.user_id == current_user.id,
                CustomerPaymentMethod.is_default == True,
            )
        )
        for pm in result.scalars().all():
            pm.is_default = False

    pm = CustomerPaymentMethod(**payload.model_dump(), user_id=current_user.id)
    db.add(pm)
    await db.commit()
    await db.refresh(pm)
    return pm


@router.put('/me/payment-methods/{pm_id}', response_model=PaymentMethodOut)
async def update_payment_method(
    pm_id: int, payload: PaymentMethodUpdate,
    current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CustomerPaymentMethod).where(CustomerPaymentMethod.id == pm_id))
    pm = result.scalar_one_or_none()
    if not pm or pm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Payment method not found')

    data = payload.model_dump(exclude_unset=True)

    if data.get('is_default'):
        result2 = await db.execute(
            select(CustomerPaymentMethod).where(
                CustomerPaymentMethod.user_id == current_user.id,
                CustomerPaymentMethod.is_default == True,
            )
        )
        for other in result2.scalars().all():
            other.is_default = False

    for field, value in data.items():
        setattr(pm, field, value)
    await db.commit()
    await db.refresh(pm)
    return pm


@router.delete('/me/payment-methods/{pm_id}', response_model=MessageOut)
async def delete_payment_method(
    pm_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CustomerPaymentMethod).where(CustomerPaymentMethod.id == pm_id))
    pm = result.scalar_one_or_none()
    if not pm or pm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Payment method not found')
    await db.delete(pm)
    await db.commit()
    return MessageOut(detail='Payment method deleted')


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post('/me/change-password')
async def change_password(
    data: PasswordChange,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail='Current password is incorrect')
    from app.security import validate_password_strength
    validate_password_strength(data.new_password)
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    return {'detail': 'Password changed successfully'}


class EmailPrefsUpdate(BaseModel):
    promotional_emails: Optional[bool] = None
    newsletter: Optional[bool] = None
    product_promotions: Optional[bool] = None
    price_drop_alerts: Optional[bool] = None
    back_in_stock_alerts: Optional[bool] = None
    review_requests: Optional[bool] = None
    loyalty_updates: Optional[bool] = None
    coupon_notifications: Optional[bool] = None


@router.get('/me/email-preferences')
async def get_email_preferences(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EmailPreference).where(EmailPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        return {
            'promotional_emails': True, 'newsletter': True,
            'product_promotions': True, 'price_drop_alerts': True,
            'back_in_stock_alerts': True, 'review_requests': True,
            'loyalty_updates': True, 'coupon_notifications': True,
        }
    return {
        'promotional_emails': pref.promotional_emails,
        'newsletter': pref.newsletter,
        'product_promotions': pref.product_promotions,
        'price_drop_alerts': pref.price_drop_alerts,
        'back_in_stock_alerts': pref.back_in_stock_alerts,
        'review_requests': pref.review_requests,
        'loyalty_updates': pref.loyalty_updates,
        'coupon_notifications': pref.coupon_notifications,
    }


@router.put('/me/email-preferences')
async def update_email_preferences(
    data: EmailPrefsUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EmailPreference).where(EmailPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = EmailPreference(user_id=current_user.id)
        db.add(pref)
    fields = ['promotional_emails', 'newsletter', 'product_promotions',
              'price_drop_alerts', 'back_in_stock_alerts', 'review_requests',
              'loyalty_updates', 'coupon_notifications']
    for field in fields:
        val = getattr(data, field, None)
        if val is not None:
            setattr(pref, field, val)
    await db.commit()
    return {'detail': 'Email preferences updated'}
