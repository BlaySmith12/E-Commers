"""Loyalty / Points System REST API — customer + admin endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import (
    LoyaltyAccount, LoyaltyTransaction, LoyaltySettings, Order, User,
)
from app.schemas import MessageOut
from app.security import AdminUser, CurrentUser
from app.audit import log_audit

router = APIRouter(prefix='/loyalty', tags=['Loyalty'])


# ----------------------------- Schemas -----------------------------
class LoyaltyAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    points_balance: int
    total_earned: int
    total_redeemed: int
    total_expired: int
    tier: str
    created_at: Optional[datetime] = None


class LoyaltyTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    type: str
    points: int
    balance_after: int
    order_id: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class LoyaltySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    value: str
    description: Optional[str] = None


class LoyaltyAdjustIn(BaseModel):
    user_id: int
    points: int  # positive = add, negative = remove
    reason: str


class RedeemIn(BaseModel):
    points: int


# ----------------------------- Helpers -----------------------------
async def _get_setting(db: AsyncSession, key: str, default: str = '0') -> str:
    result = await db.execute(select(LoyaltySettings).where(LoyaltySettings.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def _get_or_create_account(db: AsyncSession, user_id: int) -> LoyaltyAccount:
    result = await db.execute(select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id))
    account = result.scalar_one_or_none()
    if not account:
        account = LoyaltyAccount(user_id=user_id, points_balance=0, total_earned=0, total_redeemed=0, total_expired=0, tier='Bronze')
        db.add(account)
        await db.flush()
    return account


async def _update_tier(account: LoyaltyAccount):
    total = account.total_earned
    if total >= 10000:
        account.tier = 'Platinum'
    elif total >= 5000:
        account.tier = 'Gold'
    elif total >= 1000:
        account.tier = 'Silver'
    else:
        account.tier = 'Bronze'


async def _add_transaction(db, user_id, tx_type, points, balance_after, order_id=None, description=None, admin_user_id=None):
    tx = LoyaltyTransaction(
        user_id=user_id, type=tx_type, points=points,
        balance_after=balance_after, order_id=order_id,
        description=description, admin_user_id=admin_user_id,
    )
    db.add(tx)


async def award_points_for_order(db: AsyncSession, user_id: int, order: Order):
    """Award loyalty points after successful payment. Idempotent."""
    existing = await db.execute(
        select(LoyaltyTransaction).where(
            LoyaltyTransaction.user_id == user_id,
            LoyaltyTransaction.order_id == order.id,
            LoyaltyTransaction.type == 'earn',
        )
    )
    if existing.scalar_one_or_none():
        return

    points_per = int(await _get_setting(db, 'points_per_currency', '10'))
    account = await _get_or_create_account(db, user_id)

    earned = int(order.subtotal * points_per)
    if earned <= 0:
        return

    account.points_balance += earned
    account.total_earned += earned
    await _update_tier(account)
    await _add_transaction(
        db, user_id, 'earn', earned, account.points_balance,
        order_id=order.id,
        description=f'Points earned for order {order.order_number}',
    )
    await db.flush()


# ----------------------------- Customer Endpoints -----------------------------
@router.get('/me', response_model=LoyaltyAccountOut)
async def my_loyalty(current_user: CurrentUser = None, db: AsyncSession = Depends(get_db)):
    account = await _get_or_create_account(db, current_user.id)
    return account


@router.get('/me/history', response_model=List[LoyaltyTransactionOut])
async def my_loyalty_history(
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    stmt = (
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.user_id == current_user.id)
        .order_by(desc(LoyaltyTransaction.created_at))
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/me/settings')
async def my_loyalty_settings(
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    settings_keys = [
        'points_per_currency', 'redemption_rate', 'min_redemption_points',
        'max_redemption_per_order', 'min_order_for_redemption',
        'tier_bronze_min', 'tier_silver_min',
        'tier_gold_min', 'tier_platinum_min',
    ]
    result = await db.execute(
        select(LoyaltySettings).where(LoyaltySettings.key.in_(settings_keys))
    )
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}


# ----------------------------- Admin Endpoints -----------------------------
@router.get('/admin/accounts', response_model=List[LoyaltyAccountOut])
async def admin_list_accounts(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
):
    stmt = select(LoyaltyAccount)
    if search:
        stmt = stmt.join(User).where(
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    stmt = stmt.order_by(desc(LoyaltyAccount.points_balance)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/admin/transactions', response_model=List[LoyaltyTransactionOut])
async def admin_list_transactions(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
    user_id: Optional[int] = Query(None),
    tx_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(LoyaltyTransaction)
    if user_id:
        stmt = stmt.where(LoyaltyTransaction.user_id == user_id)
    if tx_type:
        stmt = stmt.where(LoyaltyTransaction.type == tx_type)
    stmt = stmt.order_by(desc(LoyaltyTransaction.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post('/admin/adjust', response_model=MessageOut)
async def admin_adjust_points(
    payload: LoyaltyAdjustIn,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    if not payload.reason or len(payload.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail='A reason is required for manual adjustments')

    account = await _get_or_create_account(db, payload.user_id)
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    old_balance = account.points_balance
    new_balance = old_balance + payload.points

    if new_balance < 0:
        raise HTTPException(status_code=400, detail='Insufficient points balance')

    account.points_balance = new_balance
    if payload.points > 0:
        account.total_earned += payload.points
    else:
        account.total_redeemed += abs(payload.points)
    await _update_tier(account)

    tx_type = 'adjust'
    await _add_transaction(
        db, payload.user_id, tx_type, payload.points, new_balance,
        description=f'Admin adjustment: {payload.reason}',
        admin_user_id=admin.id,
    )
    await db.commit()

    await log_audit(
        db=db, action="UPDATE", entity_type="LoyaltyAccount", entity_id=account.id,
        user_id=admin.id,
        details=f"Adjusted {payload.points} points for user {payload.user_id}: {payload.reason} (balance: {old_balance} -> {new_balance})",
    )
    return MessageOut(detail=f'Successfully adjusted {payload.points} points')


@router.get('/admin/settings', response_model=List[LoyaltySettingsOut])
async def admin_get_settings(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(select(LoyaltySettings).order_by(LoyaltySettings.key))
    return result.scalars().all()


@router.put('/admin/settings', response_model=MessageOut)
async def admin_update_settings(
    settings: dict,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    _VALID_KEYS = {
        'points_per_currency', 'redemption_rate', 'min_redemption_points',
        'max_redemption_per_order', 'min_order_for_redemption',
        'max_discount_percent', 'points_expiry_days', 'signup_bonus_points',
        'first_order_bonus_points', 'review_points',
        'tier_bronze_min', 'tier_silver_min', 'tier_gold_min', 'tier_platinum_min',
        'tier_bronze_multiplier', 'tier_silver_multiplier',
        'tier_gold_multiplier', 'tier_platinum_multiplier',
        'allow_points_with_coupon',
    }
    updated = 0
    for key, value in settings.items():
        if key not in _VALID_KEYS:
            continue
        result = await db.execute(select(LoyaltySettings).where(LoyaltySettings.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = str(value)
            row.updated_at = datetime.utcnow()
        else:
            db.add(LoyaltySettings(key=key, value=str(value)))
        updated += 1
    await db.commit()
    return MessageOut(detail=f'Settings updated ({updated} changed)')


@router.get('/admin/stats')
async def admin_loyalty_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    total_accounts = (await db.execute(select(func.count(LoyaltyAccount.id)))).scalar() or 0
    total_points_issued = (await db.execute(
        select(func.coalesce(func.sum(LoyaltyAccount.total_earned), 0))
    )).scalar() or 0
    total_points_redeemed = (await db.execute(
        select(func.coalesce(func.sum(LoyaltyAccount.total_redeemed), 0))
    )).scalar() or 0
    total_points_balance = (await db.execute(
        select(func.coalesce(func.sum(LoyaltyAccount.points_balance), 0))
    )).scalar() or 0

    tier_counts = {}
    for tier_name in ['Bronze', 'Silver', 'Gold', 'Platinum']:
        cnt = (await db.execute(
            select(func.count(LoyaltyAccount.id)).where(LoyaltyAccount.tier == tier_name)
        )).scalar() or 0
        tier_counts[tier_name] = cnt

    recent_txns = (await db.execute(
        select(func.count(LoyaltyTransaction.id)).where(
            LoyaltyTransaction.created_at >= datetime.utcnow() - timedelta(days=30)
        )
    )).scalar() or 0

    return {
        'total_accounts': total_accounts,
        'total_points_issued': total_points_issued,
        'total_points_redeemed': total_points_redeemed,
        'total_points_balance': total_points_balance,
        'tier_counts': tier_counts,
        'recent_transactions_30d': recent_txns,
    }


@router.get('/admin/export')
async def admin_export_points(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = None,
):
    result = await db.execute(
        select(LoyaltyAccount).join(User).order_by(desc(LoyaltyAccount.points_balance))
    )
    accounts = result.scalars().all()
    rows = []
    for a in accounts:
        user = a.user
        rows.append({
            'user_id': a.user_id,
            'name': f'{user.first_name or ""} {user.last_name or ""}'.strip() or user.username,
            'email': user.email,
            'tier': a.tier,
            'points_balance': a.points_balance,
            'total_earned': a.total_earned,
            'total_redeemed': a.total_redeemed,
            'total_expired': a.total_expired,
        })
    return rows
