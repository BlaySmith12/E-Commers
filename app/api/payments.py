"""Payment API endpoints for Paystack integration.

Handles:
- Payment initialization (creating Paystack transaction)
- Payment verification (server-side verification after redirect)
- Payment retry (for failed/expired payments)
- Webhook endpoint (receives Paystack events)
"""

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, async_session_maker
from app.models.catalog import Order, OrderItem, Payment, PaymentEvent, Product, User, Coupon, CouponUsage, LoyaltyAccount, LoyaltyTransaction, LoyaltySettings
from app.services.paystack import paystack
from app.security import CurrentUser, decode_access_token
from app.audit import log_audit
from app.activity import log_activity
from config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/payments', tags=['Payments'])


class PaymentInitIn(BaseModel):
    order_id: int
    email: str
    callback_url: Optional[str] = None


class PaymentRetryIn(BaseModel):
    payment_id: int
    email: str


class PaymentVerifyOut(BaseModel):
    success: bool
    message: str
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    payment_status: Optional[str] = None
    transaction_reference: Optional[str] = None


# ---------------------------------------------------------------------------
# Initialize Payment
# ---------------------------------------------------------------------------
@router.post('/initialize')
async def initialize_payment(
    payload: PaymentInitIn,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Initialize a Paystack payment for an existing order.

    Creates the Paystack transaction and returns the authorization URL
    for the customer to complete payment. Requires authentication and
    order ownership verification.
    """
    # Load the order
    result = await db.execute(select(Order).where(Order.id == payload.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')

    # Ownership check: customer can only pay for their own orders
    if order.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail='Not authorized to pay for this order')

    # Find or create pending payment
    pay_result = await db.execute(
        select(Payment)
        .where(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
    )
    payment = pay_result.scalars().first()

    if payment and payment.status == 'Completed':
        raise HTTPException(status_code=400, detail='Order already paid')

    # Generate unique reference
    reference = f"PN-{secrets.token_hex(12).upper()}"

    # Initialize Paystack transaction
    amount_kobo = paystack.amount_to_kobo(order.total_amount)
    callback_url = payload.callback_url or f"{paystack.base_url}/payment/callback"

    init_result = await paystack.initialize_transaction(
        email=payload.email,
        amount_kobo=amount_kobo,
        reference=reference,
        order_id=order.id,
        order_number=order.order_number,
        currency=order.currency or 'GHS',
        callback_url=callback_url,
    )

    if not init_result.get('status'):
        raise HTTPException(
            status_code=400,
            detail=init_result.get('message', 'Payment initialization failed')
        )

    data = init_result.get('data', {})

    # Update or create payment record
    if payment:
        payment.transaction_reference = reference
        payment.paystack_reference = reference
        payment.paystack_access_code = data.get('access_code', '')
        payment.access_code = data.get('access_code', '')
        payment.status = 'Pending'
        payment.customer_email = payload.email
        payment.ip_address = request.client.host if request.client else None
        payment.gateway_response = json.dumps(init_result)
        payment.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        payment = Payment(
            order_id=order.id,
            provider='paystack',
            transaction_reference=reference,
            paystack_reference=reference,
            paystack_access_code=data.get('access_code', ''),
            access_code=data.get('access_code', ''),
            amount=order.total_amount,
            currency=order.currency or 'GHS',
            status='Pending',
            payment_method=None,
            customer_email=payload.email,
            ip_address=request.client.host if request.client else None,
            gateway_response=json.dumps(init_result),
        )
        db.add(payment)

    # Update order status
    order.status = 'Pending Payment'
    order.payment_status = 'Pending'

    await db.commit()
    await db.refresh(payment)

    # Log event
    event = PaymentEvent(
        payment_id=payment.id,
        event_type='transaction.initialized',
        event_reference=reference,
        payload=json.dumps(init_result),
        processed=True,
    )
    db.add(event)
    await db.commit()

    return {
        "status": True,
        "message": "Payment initialized",
        "data": {
            "authorization_url": data.get('authorization_url', ''),
            "access_code": data.get('access_code', ''),
            "reference": reference,
            "payment_id": payment.id,
            "order_id": order.id,
        },
    }


# ---------------------------------------------------------------------------
# Verify Payment (called from frontend callback)
# ---------------------------------------------------------------------------
@router.get('/verify')
async def verify_payment(
    reference: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Verify a Paystack transaction server-side.

    This is called after the customer is redirected back from Paystack.
    It performs server-side verification and updates order/payment status.
    """
    if not reference:
        raise HTTPException(status_code=400, detail='Reference required')

    # Idempotency guard — if payment is already completed, return success immediately
    existing = await db.execute(
        select(Payment).where(Payment.transaction_reference == reference)
    )
    existing_payment = existing.scalar_one_or_none()
    if existing_payment and existing_payment.status == 'Completed':
        return PaymentVerifyOut(
            success=True,
            message='Payment already verified',
            order_id=existing_payment.order_id,
            order_number=existing_payment.order.order_number if existing_payment.order else None,
            payment_status='Completed',
            transaction_reference=reference,
        )

    # Verify with Paystack
    verify_result = await paystack.verify_transaction(reference)

    if not verify_result.get('status'):
        # Find payment to mark as failed
        pay_result = await db.execute(
            select(Payment).where(Payment.transaction_reference == reference)
        )
        payment = pay_result.scalar_one_or_none()
        if payment:
            payment.status = 'Failed'
            payment.failure_reason = verify_result.get('message', 'Verification failed')
            payment.gateway_response = json.dumps(verify_result)
            payment.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            # Update order
            if payment.order:
                payment.order.payment_status = 'Failed'
                payment.order.status = 'Payment Failed'
            await db.commit()
        return PaymentVerifyOut(
            success=False,
            message=verify_result.get('message', 'Payment verification failed'),
        )

    tx_data = verify_result.get('data', {})
    tx_status = tx_data.get('status', '').lower()
    tx_amount = tx_data.get('amount', 0) / 100  # Convert from kobo

    # Load payment record
    pay_result = await db.execute(
        select(Payment).where(Payment.transaction_reference == reference)
    )
    payment = pay_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail='Payment record not found')

    # Load order
    order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
    order = order_result.scalar_one_or_none()

    # Record the event
    event = PaymentEvent(
        payment_id=payment.id,
        event_type=f'charge.{tx_status}',
        event_reference=reference,
        gateway_response=json.dumps(verify_result),
        payload=json.dumps(verify_result),
        processed=True,
    )
    db.add(event)

    if tx_status == 'success':
        # Verify amount matches (server-side validation - critical!)
        if abs(tx_amount - order.total_amount) > 0.01:
            payment.status = 'Failed'
            payment.failure_reason = f'Amount mismatch: expected {order.total_amount}, got {tx_amount}'
            payment.gateway_response = json.dumps(verify_result)
            order.payment_status = 'Failed'
            logger.warning(
                f"Payment amount mismatch for {reference}: expected {order.total_amount}, got {tx_amount}"
            )
        else:
            # Payment successful
            payment.status = 'Completed'
            payment.paystack_reference = tx_data.get('reference', reference)
            payment.channel = tx_data.get('channel', '')
            payment.payment_method = tx_data.get('channel', 'paystack')
            paid_at_str = tx_data.get('paid_at', datetime.utcnow().isoformat()).replace('Z', '+00:00')
            parsed = datetime.fromisoformat(paid_at_str)
            payment.paid_at = parsed.replace(tzinfo=None)
            payment.gateway_response = json.dumps(verify_result)
            payment.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            # Update order
            order.status = 'Paid'
            order.payment_status = 'Paid'

            # Record coupon usage
            if order.coupon_id:
                try:
                    coupon_usage = CouponUsage(
                        coupon_id=order.coupon_id,
                        user_id=order.user_id,
                        order_id=order.id,
                        discount_amount=order.discount,
                    )
                    db.add(coupon_usage)
                except Exception:
                    pass

            # Clear cart, update inventory only after successful payment
            for item in order.items:
                product = (await db.execute(
                    select(Product).where(Product.id == item.product_id)
                )).scalar_one_or_none()
                if product:
                    product.stock = max(0, product.stock - item.quantity)

            # Award loyalty points
            try:
                await _award_loyalty_points(order, db)
            except Exception:
                logger.exception(f"Failed to award loyalty points for order {order.order_number}")

        await db.commit()

        # Activity log for successful payment
        try:
            await log_activity(
                db=db,
                activity_type="payment_completed",
                description=f"Payment for order #{order.order_number} was successfully completed",
                entity_type="Order",
                entity_id=order.id,
                entity_number=order.order_number,
                extra_data={"amount": order.total_amount, "reference": reference},
            )
            await db.commit()
        except Exception:
            pass

        # Send payment success email (fire-and-forget)
        try:
            from app.services.email_service import send_payment_success_email
            async with async_session_maker() as email_db:
                await send_payment_success_email(email_db, order, payment)
                await email_db.commit()
        except Exception:
            logger.exception("Failed to send payment success email")

        return PaymentVerifyOut(
            success=True,
            message='Payment verified successfully',
            order_id=order.id,
            order_number=order.order_number,
            payment_status='Paid',
            transaction_reference=reference,
        )
    else:
        # Payment failed
        payment.status = 'Failed'
        payment.failure_reason = tx_data.get('gateway_response', 'Payment not successful')
        payment.gateway_response = json.dumps(verify_result)
        payment.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        if order:
            order.payment_status = 'Failed'
            order.status = 'Payment Failed'

        await db.commit()

        # Activity log for failed payment
        try:
            await log_activity(
                db=db,
                activity_type="payment_failed",
                description=f"Payment for order #{order.order_number} failed",
                entity_type="Order",
                entity_id=order.id if order else None,
                entity_number=order.order_number if order else None,
                extra_data={"reference": reference, "reason": tx_data.get('gateway_response', '')},
            )
            await db.commit()
        except Exception:
            pass

        # Send payment failed email (fire-and-forget)
        try:
            from app.services.email_service import send_payment_failed_email
            async with async_session_maker() as email_db:
                await send_payment_failed_email(email_db, order, payment, reason=tx_data.get('gateway_response', ''))
                await email_db.commit()
        except Exception:
            logger.exception("Failed to send payment failed email")

        return PaymentVerifyOut(
            success=False,
            message=tx_data.get('gateway_response', 'Payment was not successful'),
            order_id=order.id,
            order_number=order.order_number,
            payment_status='Failed',
            transaction_reference=reference,
        )


# ---------------------------------------------------------------------------
# Get Payment by Order
# ---------------------------------------------------------------------------
@router.get('/order/{order_id}')
async def get_payment_by_order(
    order_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest payment record for an order. Requires authentication and order ownership."""
    result = await db.execute(
        select(Payment)
        .where(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc())
    )
    payment = result.scalars().first()
    if not payment:
        raise HTTPException(status_code=404, detail='No payment found for this order')

    # Ownership check
    order = await db.execute(select(Order).where(Order.id == order_id))
    order = order.scalar_one_or_none()
    if order and order.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail='Not authorized to view this payment')

    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "provider": payment.provider,
        "transaction_reference": payment.transaction_reference,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,
        "payment_method": payment.payment_method,
        "channel": payment.channel,
        "customer_email": payment.customer_email,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }


# ---------------------------------------------------------------------------
# Retry Payment
# ---------------------------------------------------------------------------
@router.post('/retry')
async def retry_payment(
    payload: PaymentRetryIn,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed payment for an existing order.

    Requires authentication and order ownership verification.
    """
    # Load existing payment
    result = await db.execute(
        select(Payment).where(Payment.id == payload.payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail='Payment not found')

    if payment.status == 'Completed':
        raise HTTPException(status_code=400, detail='Payment already completed')

    # Load order
    order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')

    # Ownership check
    if order.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail='Not authorized to retry this payment')

    # Generate new reference
    reference = f"PN-{secrets.token_hex(12).upper()}"

    # Initialize new transaction
    amount_kobo = paystack.amount_to_kobo(order.total_amount)
    callback_url = f"{paystack.base_url}/payment/callback"

    init_result = await paystack.initialize_transaction(
        email=payload.email,
        amount_kobo=amount_kobo,
        reference=reference,
        order_id=order.id,
        order_number=order.order_number,
        currency=order.currency or 'GHS',
        callback_url=callback_url,
    )

    if not init_result.get('status'):
        raise HTTPException(
            status_code=400,
            detail=init_result.get('message', 'Payment retry failed')
        )

    data = init_result.get('data', {})

    # Create new payment record (keep old one for history)
    new_payment = Payment(
        order_id=order.id,
        provider='paystack',
        transaction_reference=reference,
        paystack_reference=reference,
        paystack_access_code=data.get('access_code', ''),
        access_code=data.get('access_code', ''),
        amount=order.total_amount,
        currency=order.currency or 'GHS',
        status='Pending',
        payment_method=None,
        customer_email=payload.email,
        ip_address=request.client.host if request.client else None,
        gateway_response=json.dumps(init_result),
    )
    db.add(new_payment)

    # Update order
    order.status = 'Pending Payment'
    order.payment_status = 'Pending'

    await db.commit()
    await db.refresh(new_payment)

    return {
        "status": True,
        "message": "Payment retry initialized",
        "data": {
            "authorization_url": data.get('authorization_url', ''),
            "access_code": data.get('access_code', ''),
            "reference": reference,
            "payment_id": new_payment.id,
            "order_id": order.id,
        },
    }


# ---------------------------------------------------------------------------
# Webhook Endpoint
# ---------------------------------------------------------------------------
@router.post('/webhook')
async def paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Paystack webhook events.

    Validates the webhook signature, processes charge.success events,
    and updates order/payment status. Idempotent - won't process
    duplicate events.
    """
    body = await request.body()
    signature = request.headers.get('x-paystack-signature', '')

    # Verify signature — fail closed if webhook secret is not configured
    if not config.PAYSTACK_WEBHOOK_SECRET:
        logger.critical("PAYSTACK_WEBHOOK_SECRET is not configured — rejecting webhook")
        raise HTTPException(status_code=500, detail='Webhook not configured')
    if not paystack.verify_webhook_signature(body, signature):
        logger.warning("Invalid Paystack webhook signature from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=400, detail='Invalid signature')

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid JSON payload')

    event_type = event.get('event', '')
    event_data = event.get('data', {})
    reference = event_data.get('reference', '')

    logger.info(f"Paystack webhook: {event_type} for {reference}")

    if not reference:
        return {"status": "ok", "message": "No reference in event"}

    # Load payment by reference
    result = await db.execute(
        select(Payment).where(Payment.transaction_reference == reference)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        # Try paystack_reference
        result = await db.execute(
            select(Payment).where(Payment.paystack_reference == reference)
        )
        payment = result.scalar_one_or_none()

    if not payment:
        logger.warning(f"Webhook: No payment found for reference {reference}")
        return {"status": "ok", "message": "Payment not found"}

    # Check for duplicate event processing (idempotency)
    existing_event = await db.execute(
        select(PaymentEvent).where(
            PaymentEvent.payment_id == payment.id,
            PaymentEvent.event_type == event_type,
            PaymentEvent.event_reference == reference,
        )
    )
    if existing_event.scalar_one_or_none():
        logger.info(f"Webhook: Duplicate event {event_type} for {reference}")
        return {"status": "ok", "message": "Event already processed"}

    # Record the event
    db_event = PaymentEvent(
        payment_id=payment.id,
        event_type=event_type,
        event_reference=reference,
        gateway_response=event_data.get('gateway_response', ''),
        payload=json.dumps(event),
        processed=True,
    )
    db.add(db_event)

    # Process based on event type
    if event_type == 'charge.success':
        await _process_successful_payment(payment, event_data, db)
    elif event_type == 'charge.failed':
        await _process_failed_payment(payment, event_data, db)
    elif event_type == 'charge.pending':
        await _process_pending_payment(payment, event_data, db)

    await db.commit()

    return {"status": "ok", "message": "Webhook processed"}


async def _process_successful_payment(payment: Payment, event_data: dict, db: AsyncSession):
    """Process a successful payment webhook event."""
    if payment.status == 'Completed':
        return  # Already processed (idempotent)

    tx_amount = event_data.get('amount', 0) / 100

    # Load order
    order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
    order = order_result.scalar_one_or_none()

    if not order:
        logger.error(f"Webhook success: Order {payment.order_id} not found")
        return

    # Verify amount matches
    if abs(tx_amount - order.total_amount) > 0.01:
        logger.warning(
            f"Webhook amount mismatch: expected {order.total_amount}, got {tx_amount}"
        )
        payment.status = 'Failed'
        payment.failure_reason = f'Amount mismatch in webhook'
        order.payment_status = 'Failed'
        return

    # Mark as paid
    payment.status = 'Completed'
    payment.paystack_reference = event_data.get('reference', payment.transaction_reference)
    payment.channel = event_data.get('channel', '')
    payment.payment_method = event_data.get('channel', 'paystack')
    paid_at = event_data.get('paid_at', '')
    if paid_at:
        try:
            payment.paid_at = datetime.fromisoformat(paid_at.replace('Z', '+00:00')).replace(tzinfo=None)
        except (ValueError, TypeError):
            payment.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        payment.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
    payment.gateway_response = json.dumps(event_data)
    payment.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Update order
    order.status = 'Paid'
    order.payment_status = 'Paid'

    # Record coupon usage
    if order.coupon_id:
        try:
            coupon_usage = CouponUsage(
                coupon_id=order.coupon_id,
                user_id=order.user_id,
                order_id=order.id,
                discount_amount=order.discount,
            )
            db.add(coupon_usage)
        except Exception:
            pass

    # Decrement inventory (only after verified payment)
    for item in order.items:
        product = (await db.execute(
            select(Product).where(Product.id == item.product_id)
        )).scalar_one_or_none()
        if product:
            product.stock = max(0, product.stock - item.quantity)

    # Award loyalty points
    try:
        await _award_loyalty_points(order, db)
    except Exception:
        logger.exception(f"Failed to award loyalty points via webhook for order {order.order_number}")

    logger.info(f"Webhook: Payment {payment.id} marked as Completed via webhook")

    # Send payment success email (fire-and-forget)
    try:
        from app.services.email_service import send_payment_success_email
        async with async_session_maker() as email_db:
            await send_payment_success_email(email_db, order, payment)
            await email_db.commit()
    except Exception:
        logger.exception("Failed to send payment success email via webhook")

    # Activity log for webhook payment success
    try:
        await log_activity(
            db=db,
            activity_type="payment_completed",
            description=f"Payment for order #{order.order_number} was successfully completed",
            entity_type="Order",
            entity_id=order.id,
            entity_number=order.order_number,
            extra_data={"amount": order.total_amount, "via": "webhook"},
        )
    except Exception:
        pass


async def _process_failed_payment(payment: Payment, event_data: dict, db: AsyncSession):
    """Process a failed payment webhook event."""
    if payment.status in ('Completed', 'Failed'):
        return  # Already processed

    payment.status = 'Failed'
    payment.failure_reason = event_data.get('gateway_response', 'Payment failed')
    payment.gateway_response = json.dumps(event_data)
    payment.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Update order
    order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.payment_status = 'Failed'
        order.status = 'Payment Failed'

        # Send payment failed email (fire-and-forget)
        try:
            from app.services.email_service import send_payment_failed_email
            async with async_session_maker() as email_db:
                await send_payment_failed_email(email_db, order, payment, reason=payment.failure_reason or "")
                await email_db.commit()
        except Exception:
            logger.exception("Failed to send payment failed email via webhook")

    logger.info(f"Webhook: Payment {payment.id} marked as Failed via webhook")


async def _process_pending_payment(payment: Payment, event_data: dict, db: AsyncSession):
    """Process a pending payment webhook event."""
    if payment.status == 'Completed':
        return  # Don't downgrade from completed

    payment.status = 'Pending'
    payment.gateway_response = json.dumps(event_data)
    payment.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    logger.info(f"Webhook: Payment {payment.id} status updated to Pending via webhook")


async def _award_loyalty_points(order, db: AsyncSession):
    """Award loyalty points for a paid order. Idempotent."""
    if not order.user_id or order.total_amount <= 0:
        return

    # Check if points already awarded for this order
    existing = await db.execute(
        select(LoyaltyTransaction).where(
            LoyaltyTransaction.order_id == order.id,
            LoyaltyTransaction.type == 'earn',
        )
    )
    if existing.scalar_one_or_none():
        return  # Already awarded

    # Get loyalty settings
    points_per_currency = 10
    try:
        settings_result = await db.execute(
            select(LoyaltySettings).where(LoyaltySettings.key == 'points_per_currency')
        )
        setting_row = settings_result.scalar_one_or_none()
        if setting_row:
            points_per_currency = int(setting_row.value)
    except Exception:
        pass

    # Get tier multiplier
    multiplier = 1.0
    tier = 'Bronze'
    try:
        acct_result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == order.user_id)
        )
        account = acct_result.scalar_one_or_none()
        if account:
            tier = account.tier or 'Bronze'
    except Exception:
        account = None

    try:
        tier_key = f'tier_{tier.lower()}_multiplier'
        settings_result = await db.execute(
            select(LoyaltySettings).where(LoyaltySettings.key == tier_key)
        )
        setting_row = settings_result.scalar_one_or_none()
        if setting_row:
            multiplier = float(setting_row.value)
    except Exception:
        pass

    # Calculate points
    base_points = int(order.total_amount * points_per_currency)
    earned_points = int(base_points * multiplier)
    if earned_points <= 0:
        return

    # Get or create loyalty account
    if not account:
        account = LoyaltyAccount(user_id=order.user_id, points_balance=0, total_earned=0, total_redeemed=0, total_expired=0, tier='Bronze')
        db.add(account)
        await db.flush()

    account.points_balance += earned_points
    account.total_earned += earned_points

    # Determine tier
    try:
        tier_thresholds = {
            'Platinum': 10000,
            'Gold': 5000,
            'Silver': 1000,
        }
        for t_name, t_min in tier_thresholds.items():
            sr = await db.execute(select(LoyaltySettings).where(LoyaltySettings.key == f'tier_{t_name.lower()}_min'))
            sr_row = sr.scalar_one_or_none()
            if sr_row:
                t_min = int(sr_row.value)
            if account.total_earned >= t_min:
                account.tier = t_name
                break
    except Exception:
        pass

    await db.add(LoyaltyTransaction(
        user_id=order.user_id,
        type='earn',
        points=earned_points,
        balance_after=account.points_balance,
        order_id=order.id,
        description=f'Earned {earned_points} points for order {order.order_number} (GHS {order.total_amount:.2f})',
    ))
    await db.flush()

    # Send loyalty points earned email (fire-and-forget)
    try:
        from app.services.email_service import send_loyalty_points_email
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            async with async_session_maker() as email_db:
                await send_loyalty_points_email(email_db, user, 'earn', earned_points, account.points_balance, description=f'Earned for order {order.order_number}', order_number=order.order_number)
                await email_db.commit()
    except Exception:
        logger.exception("Failed to send loyalty points earned email")

    # Activity log for loyalty points earned
    try:
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        actor_name = (((user.first_name or '') + ' ' + (user.last_name or '')).strip() or user.email) if user else "Customer"
        await log_activity(
            db=db,
            activity_type="loyalty_points_earned",
            description=f"{actor_name} earned {earned_points} loyalty points for order #{order.order_number}",
            entity_type="User",
            entity_id=order.user_id,
            entity_number=order.order_number,
            actor_name=actor_name,
            actor_id=order.user_id,
            extra_data={"points": earned_points, "order_total": order.total_amount},
        )
    except Exception:
        pass
