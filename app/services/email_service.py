"""Production-ready email notification service.

Architecture:
  queue_email()  -->  EmailLog (DB, status=queued)  -->  asyncio.Queue
  Background worker  -->  SMTP send  -->  Update EmailLog (sent/failed)

Duplicate prevention: unique (email_type, entity_type, entity_id) check.
Fireside: emails never block or fail the calling API endpoint.
"""

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.catalog import EmailLog, EmailPreference, User
from config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 environment for email templates
# ---------------------------------------------------------------------------
_EMAIL_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_EMAIL_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ---------------------------------------------------------------------------
# Public API – call this from any endpoint
# ---------------------------------------------------------------------------
async def queue_email(
    db: AsyncSession,
    *,
    recipient_email: str,
    email_type: str,
    subject: str,
    template_name: str,
    context: Dict[str, Any],
    recipient_user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    skip_duplicate_check: bool = False,
) -> Optional[EmailLog]:
    """Queue an email for background delivery.

    Returns the EmailLog entry, or None if skipped (duplicate / no SMTP).
    Never raises – failures are logged and swallowed so callers are safe.
    """
    if not config.SMTP_HOST or not config.EMAIL_FROM_ADDRESS:
        logger.debug("SMTP not configured – skipping email %s", email_type)
        return None

    # Duplicate prevention
    if not skip_duplicate_check and entity_type and entity_id:
        dup = await db.execute(
            select(EmailLog).where(
                EmailLog.email_type == email_type,
                EmailLog.entity_type == entity_type,
                EmailLog.entity_id == entity_id,
                EmailLog.status.in_(["queued", "sending", "sent", "delivered"]),
            )
        )
        if dup.scalar_one_or_none():
            logger.info("Duplicate email skipped: %s %s/%s", email_type, entity_type, entity_id)
            return None

    # Check customer email preferences (skip for essential transactional emails)
    _ESSENTIAL_TYPES = {
        "welcome", "password_reset", "password_changed",
        "order_confirmation", "payment_success", "payment_failed",
        "order_status_changed", "order_cancelled", "refund",
        "broadcast_order",
    }
    if recipient_user_id and email_type not in _ESSENTIAL_TYPES:
        pref = await db.execute(
            select(EmailPreference).where(EmailPreference.user_id == recipient_user_id)
        )
        pref = pref.scalar_one_or_none()
        if pref:
            _pref_map = {
                "promotional_emails": ["promotional", "newsletter", "broadcast_promotional"],
                "newsletter": ["newsletter", "broadcast_newsletter"],
                "product_promotions": ["promotional", "broadcast_product"],
                "price_drop_alerts": ["price_drop", "broadcast_price_drop"],
                "back_in_stock_alerts": ["stock_alert", "broadcast_stock"],
                "review_requests": ["review_request", "broadcast_review"],
                "loyalty_updates": ["loyalty_points_earned", "loyalty_points_redeemed", "broadcast_loyalty"],
                "coupon_notifications": ["coupon_used", "coupon_expiring", "broadcast_coupon"],
            }
            for col, types in _pref_map.items():
                if email_type in types and not getattr(pref, col, True):
                    logger.info("Email %s skipped – user %s opted out", email_type, recipient_user_id)
                    return None

    # Render HTML
    try:
        html_body = _render_template(template_name, context)
    except Exception:
        logger.exception("Failed to render email template %s", template_name)
        return None

    # Persist log entry
    log = EmailLog(
        recipient_email=recipient_email,
        recipient_user_id=recipient_user_id,
        email_type=email_type,
        entity_type=entity_type,
        entity_id=entity_id,
        subject=subject,
        status="queued",
        created_at=datetime.utcnow(),
    )
    db.add(log)
    await db.flush()
    log_id = log.id

    # Enqueue for background worker
    _email_queue.put_nowait({
        "log_id": log_id,
        "recipient": recipient_email,
        "subject": subject,
        "html": html_body,
    })
    return log


async def queue_email_direct(
    *,
    recipient_email: str,
    email_type: str,
    subject: str,
    html_body: str,
    recipient_user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    skip_duplicate_check: bool = False,
) -> Optional[EmailLog]:
    """Queue an already-rendered email (for admin test sends, etc.)."""
    if not config.SMTP_HOST or not config.EMAIL_FROM_ADDRESS:
        return None

    if not skip_duplicate_check and entity_type and entity_id:
        async with async_session_maker() as db:
            dup = await db.execute(
                select(EmailLog).where(
                    EmailLog.email_type == email_type,
                    EmailLog.entity_type == entity_type,
                    EmailLog.entity_id == entity_id,
                    EmailLog.status.in_(["queued", "sending", "sent", "delivered"]),
                )
            )
            if dup.scalar_one_or_none():
                return None

    async with async_session_maker() as db:
        log = EmailLog(
            recipient_email=recipient_email,
            recipient_user_id=recipient_user_id,
            email_type=email_type,
            entity_type=entity_type,
            entity_id=entity_id,
            subject=subject,
            status="queued",
            created_at=datetime.utcnow(),
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        log_id = log.id

    _email_queue.put_nowait({
        "log_id": log_id,
        "recipient": recipient_email,
        "subject": subject,
        "html": html_body,
    })
    return log


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------
def _render_template(name: str, context: Dict[str, Any]) -> str:
    base_ctx = {
        "store_name": config.EMAIL_FROM_NAME or "ASAH'S PRIMENEST",
        "store_url": config.BASE_URL,
        "support_email": config.EMAIL_REPLY_TO or config.EMAIL_FROM_ADDRESS or "",
        "year": datetime.utcnow().year,
        "brand_color": "#F2660F",
        "dark_color": "#121010",
        "light_bg": "#F6F9F9",
        "border_color": "#DBD2CB",
    }
    base_ctx.update(context)
    template = _jinja_env.get_template(name)
    return template.render(**base_ctx)


# ---------------------------------------------------------------------------
# In-memory async queue + background worker
# ---------------------------------------------------------------------------
_email_queue: asyncio.Queue = asyncio.Queue()
_worker_task: Optional[asyncio.Task] = None
_MAX_RETRIES = 3


async def _background_worker():
    """Continuously process emails from the queue."""
    while True:
        item = await _email_queue.get()
        log_id = item["log_id"]
        try:
            async with async_session_maker() as db:
                result = await db.execute(select(EmailLog).where(EmailLog.id == log_id))
                log = result.scalar_one_or_none()
                if not log or log.status not in ("queued", "failed"):
                    continue

                log.status = "sending"
                await db.commit()

                _send_smtp(
                    to_email=log.recipient_email,
                    subject=log.subject,
                    html_body=item["html"],
                )

                log.status = "sent"
                log.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                log.retry_count = 0
                await db.commit()
                logger.info("Email sent: %s -> %s", log.email_type, log.recipient_email)

        except Exception as exc:
            logger.exception("Email send failed for log_id=%s", log_id)
            try:
                async with async_session_maker() as db:
                    result = await db.execute(select(EmailLog).where(EmailLog.id == log_id))
                    log = result.scalar_one_or_none()
                    if log:
                        log.retry_count = (log.retry_count or 0) + 1
                        if log.retry_count >= _MAX_RETRIES:
                            log.status = "failed"
                        else:
                            log.status = "queued"
                        log.failure_reason = str(exc)[:500]
                        await db.commit()
            except Exception:
                logger.exception("Failed to update email log after error")
        finally:
            _email_queue.task_done()


def _send_smtp(to_email: str, subject: str, html_body: str):
    """Send an email via SMTP (blocking, called in thread-safe context)."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM_ADDRESS}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = config.EMAIL_REPLY_TO or config.EMAIL_FROM_ADDRESS
    msg["X-Mailer"] = "ASAH'S PRIMENEST Mailer"

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
        if config.SMTP_USE_TLS:
            server.starttls(context=context)
        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(config.EMAIL_FROM_ADDRESS, [to_email], msg.as_string())


async def start_email_worker():
    """Start the background email worker. Call on app startup."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_background_worker())
    logger.info("Email background worker started")


async def stop_email_worker():
    """Gracefully stop the email worker. Call on app shutdown."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None
    logger.info("Email background worker stopped")


async def retry_failed_emails():
    """Pick up any previously failed emails that haven't exceeded max retries."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(EmailLog).where(
                EmailLog.status == "queued",
                EmailLog.retry_count < _MAX_RETRIES,
            ).order_by(EmailLog.created_at.asc()).limit(50)
        )
        logs = result.scalars().all()
        for log in logs:
            _email_queue.put_nowait({
                "log_id": log.id,
                "recipient": log.recipient_email,
                "subject": log.subject,
                "html": "(placeholder – re-render on retry not supported)",
            })
    if logs:
        logger.info("Re-queued %d failed emails for retry", len(logs))


# ---------------------------------------------------------------------------
# Convenience helpers for common email types
# ---------------------------------------------------------------------------

async def send_welcome_email(db: AsyncSession, user: User):
    """Send welcome email after registration."""
    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    await queue_email(
        db,
        recipient_email=user.email,
        recipient_user_id=user.id,
        email_type="welcome",
        subject=f"Welcome to {config.EMAIL_FROM_NAME}!",
        template_name="welcome.html",
        context={"customer_name": name, "customer_email": user.email},
        entity_type="User",
        entity_id=user.id,
    )


async def send_password_reset_email(db: AsyncSession, user: User, token: str):
    """Send password reset email."""
    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    reset_path = "/admin/reset-password" if user.is_admin else "/reset-password"
    reset_url = f"{config.BASE_URL}{reset_path}?token={token}"
    await queue_email(
        db,
        recipient_email=user.email,
        recipient_user_id=user.id,
        email_type="password_reset",
        subject="Reset Your Password",
        template_name="password_reset.html",
        context={"customer_name": name, "reset_url": reset_url, "token": token},
        entity_type="User",
        entity_id=user.id,
    )


async def send_password_changed_email(db: AsyncSession, user: User):
    """Notify user that password was changed."""
    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    await queue_email(
        db,
        recipient_email=user.email,
        recipient_user_id=user.id,
        email_type="password_changed",
        subject="Your Password Was Changed",
        template_name="password_changed.html",
        context={"customer_name": name},
        entity_type="User",
        entity_id=user.id,
    )


async def send_order_confirmation_email(db: AsyncSession, order):
    """Send order confirmation email after checkout."""
    user = order.customer if hasattr(order, 'customer') and order.customer else None
    customer_name = order.customer_name or (
        ((user.first_name or "") + " " + (user.last_name or "")).strip() if user else ""
    ) or "Customer"
    customer_email = order.customer_email or (user.email if user else None)
    if not customer_email:
        return

    items = []
    for item in (order.items or []):
        items.append({
            "name": item.snapshot_name or (item.product.name if item.product else "Product"),
            "image": item.snapshot_image or (item.product.images[0].image_url if item.product and item.product.images else ""),
            "quantity": item.quantity,
            "price": f"{item.price:.2f}",
            "total": f"{(item.price * item.quantity):.2f}",
            "brand": item.snapshot_brand or "",
        })

    addr = None
    if order.shipping_address:
        addr = ", ".join(filter(None, [
            getattr(order.shipping_address, "street", None),
            getattr(order.shipping_address, "city", None),
            getattr(order.shipping_address, "state", None),
            getattr(order.shipping_address, "country", None),
        ]))

    base_url = config.BASE_URL
    await queue_email(
        db,
        recipient_email=customer_email,
        recipient_user_id=order.user_id,
        email_type="order_confirmation",
        subject=f"Order Confirmed – #{order.order_number}",
        template_name="order_confirmation.html",
        context={
            "customer_name": customer_name,
            "order_number": order.order_number,
            "order_date": order.created_at.strftime("%B %d, %Y") if order.created_at else "",
            "order_status": order.status,
            "payment_status": getattr(order, "payment_status", "Pending"),
            "items": items,
            "subtotal": f"{order.subtotal:.2f}",
            "discount": f"{order.discount:.2f}" if order.discount else "0.00",
            "shipping_fee": f"{order.shipping_fee:.2f}",
            "tax": f"{order.tax:.2f}",
            "total": f"{order.total_amount:.2f}",
            "currency": getattr(order, "currency", "GHS"),
            "shipping_address": addr or "Not provided",
            "payment_method": getattr(order, "payment_method", "Online"),
            "order_url": f"{base_url}/order-tracking",
            "coupon_code": getattr(order, "coupon_code", None),
            "points_used": getattr(order, "points_used", 0) or 0,
            "points_discount": f"{getattr(order, 'points_discount', 0):.2f}" if getattr(order, "points_discount", 0) else None,
        },
        entity_type="Order",
        entity_id=order.id,
    )


async def send_payment_success_email(db: AsyncSession, order, payment):
    """Send payment success email."""
    user = order.customer if hasattr(order, 'customer') and order.customer else None
    customer_name = order.customer_name or (
        ((user.first_name or "") + " " + (user.last_name or "")).strip() if user else ""
    ) or "Customer"
    customer_email = payment.customer_email or order.customer_email or (user.email if user else None)
    if not customer_email:
        return

    await queue_email(
        db,
        recipient_email=customer_email,
        recipient_user_id=order.user_id,
        email_type="payment_success",
        subject=f"Payment Confirmed – Order #{order.order_number}",
        template_name="payment_success.html",
        context={
            "customer_name": customer_name,
            "order_number": order.order_number,
            "amount": f"{payment.amount:.2f}",
            "currency": getattr(payment, "currency", "GHS"),
            "payment_method": payment.payment_method or payment.channel or "Online",
            "payment_reference": payment.transaction_reference or "",
            "paid_at": payment.paid_at.strftime("%B %d, %Y at %I:%M %p") if payment.paid_at else "",
            "order_url": f"{config.BASE_URL}/order-tracking",
        },
        entity_type="Payment",
        entity_id=payment.id,
    )


async def send_payment_failed_email(db: AsyncSession, order, payment, reason: str = ""):
    """Send payment failed email."""
    user = order.customer if hasattr(order, 'customer') and order.customer else None
    customer_name = order.customer_name or (
        ((user.first_name or "") + " " + (user.last_name or "")).strip() if user else ""
    ) or "Customer"
    customer_email = payment.customer_email or order.customer_email or (user.email if user else None)
    if not customer_email:
        return

    await queue_email(
        db,
        recipient_email=customer_email,
        recipient_user_id=order.user_id,
        email_type="payment_failed",
        subject=f"Payment Failed – Order #{order.order_number}",
        template_name="payment_failed.html",
        context={
            "customer_name": customer_name,
            "order_number": order.order_number,
            "amount": f"{order.total_amount:.2f}",
            "currency": getattr(order, "currency", "GHS"),
            "reason": reason or "Payment was not completed",
            "retry_url": f"{config.BASE_URL}/order-tracking",
        },
        entity_type="Payment",
        entity_id=payment.id,
    )


async def send_order_status_email(db: AsyncSession, order, old_status: str, new_status: str):
    """Send order status change notification."""
    user = order.customer if hasattr(order, 'customer') and order.customer else None
    customer_name = order.customer_name or (
        ((user.first_name or "") + " " + (user.last_name or "")).strip() if user else ""
    ) or "Customer"
    customer_email = order.customer_email or (user.email if user else None)
    if not customer_email:
        return

    _STATUS_TEMPLATES = {
        "Processing": ("order_processing.html", "Your Order is Being Processed"),
        "Shipped": ("order_shipped.html", "Your Order Has Been Shipped!"),
        "Out for Delivery": ("order_out_for_delivery.html", "Your Order is Out for Delivery"),
        "Delivered": ("order_delivered.html", "Your Order Has Been Delivered!"),
        "Cancelled": ("order_cancelled.html", "Order Cancelled"),
        "On Hold": ("order_on_hold.html", "Your Order is On Hold"),
        "Refunded": ("order_refunded.html", "Your Order Has Been Refunded"),
    }
    template_file, subject = _STATUS_TEMPLATES.get(
        new_status,
        ("order_status_update.html", f"Order Status Update – #{order.order_number}"),
    )

    tracking_number = getattr(order, "tracking_number", None)
    tracking_url = getattr(order, "tracking_url", None)
    courier = getattr(order, "shipping_provider", None)

    await queue_email(
        db,
        recipient_email=customer_email,
        recipient_user_id=order.user_id,
        email_type="order_status_changed",
        subject=subject,
        template_name=template_file,
        context={
            "customer_name": customer_name,
            "order_number": order.order_number,
            "old_status": old_status,
            "new_status": new_status,
            "order_date": order.created_at.strftime("%B %d, %Y") if order.created_at else "",
            "total": f"{order.total_amount:.2f}",
            "currency": getattr(order, "currency", "GHS"),
            "tracking_number": tracking_number,
            "tracking_url": tracking_url,
            "courier": courier,
            "order_url": f"{config.BASE_URL}/order-tracking",
            "is_delivered": new_status == "Delivered",
            "is_shipped": new_status in ("Shipped", "Out for Delivery"),
        },
        entity_type="Order",
        entity_id=order.id,
    )


async def send_order_cancelled_email(db: AsyncSession, order, cancelled_by: str = "Customer"):
    """Send order cancellation email."""
    user = order.customer if hasattr(order, 'customer') and order.customer else None
    customer_name = order.customer_name or (
        ((user.first_name or "") + " " + (user.last_name or "")).strip() if user else ""
    ) or "Customer"
    customer_email = order.customer_email or (user.email if user else None)
    if not customer_email:
        return

    await queue_email(
        db,
        recipient_email=customer_email,
        recipient_user_id=order.user_id,
        email_type="order_cancelled",
        subject=f"Order Cancelled – #{order.order_number}",
        template_name="order_cancelled.html",
        context={
            "customer_name": customer_name,
            "order_number": order.order_number,
            "cancelled_by": cancelled_by,
            "cancellation_date": datetime.utcnow().strftime("%B %d, %Y"),
            "total": f"{order.total_amount:.2f}",
            "currency": getattr(order, "currency", "GHS"),
            "order_url": f"{config.BASE_URL}/order-tracking",
        },
        entity_type="Order",
        entity_id=order.id,
    )


async def send_refund_email(db: AsyncSession, order, payment, refund_status: str = "processed"):
    """Send refund notification email."""
    user = order.customer if hasattr(order, 'customer') and order.customer else None
    customer_name = order.customer_name or (
        ((user.first_name or "") + " " + (user.last_name or "")).strip() if user else ""
    ) or "Customer"
    customer_email = order.customer_email or (user.email if user else None)
    if not customer_email:
        return

    await queue_email(
        db,
        recipient_email=customer_email,
        recipient_user_id=order.user_id,
        email_type="refund",
        subject=f"Refund {refund_status.title()} – Order #{order.order_number}",
        template_name="refund.html",
        context={
            "customer_name": customer_name,
            "order_number": order.order_number,
            "refund_amount": f"{payment.refund_amount:.2f}" if payment.refund_amount else f"{payment.amount:.2f}",
            "currency": getattr(payment, "currency", "GHS"),
            "refund_status": refund_status,
            "refund_reason": getattr(payment, "refund_reason", None),
            "refund_reference": getattr(payment, "refund_reference", None),
            "order_url": f"{config.BASE_URL}/order-tracking",
        },
        entity_type="Payment",
        entity_id=payment.id,
    )


async def send_loyalty_points_email(
    db: AsyncSession, user: User, tx_type: str, points: int,
    balance_after: int, description: str = "", order_number: str = "",
):
    """Send loyalty points earned/redeemed notification."""
    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    is_earned = tx_type in ("earn", "bonus")
    subject = f"You Earned {points} Loyalty Points!" if is_earned else f"{abs(points)} Loyalty Points Redeemed"
    template = "loyalty_points_earned.html" if is_earned else "loyalty_points_redeemed.html"

    await queue_email(
        db,
        recipient_email=user.email,
        recipient_user_id=user.id,
        email_type="loyalty_points_earned" if is_earned else "loyalty_points_redeemed",
        subject=subject,
        template_name=template,
        context={
            "customer_name": name,
            "points": abs(points),
            "tx_type": tx_type,
            "balance_after": balance_after,
            "description": description,
            "order_number": order_number,
            "loyalty_url": f"{config.BASE_URL}/customer/loyalty",
        },
        entity_type="User",
        entity_id=user.id,
    )


async def send_coupon_used_email(
    db: AsyncSession, user: User, coupon_code: str, discount_amount: float, order_number: str,
):
    """Send coupon used notification."""
    name = ((user.first_name or "") + " " + (user.last_name or "")).strip() or user.email
    await queue_email(
        db,
        recipient_email=user.email,
        recipient_user_id=user.id,
        email_type="coupon_used",
        subject=f"Coupon {coupon_code} Applied Successfully!",
        template_name="coupon_used.html",
        context={
            "customer_name": name,
            "coupon_code": coupon_code,
            "discount_amount": f"{discount_amount:.2f}",
            "order_number": order_number,
            "currency": "GHS",
            "shop_url": f"{config.BASE_URL}/shop",
        },
        entity_type="User",
        entity_id=user.id,
    )


async def send_review_request_email(db: AsyncSession, order):
    """Send review request after delivery."""
    user = order.customer if hasattr(order, 'customer') and order.customer else None
    customer_name = order.customer_name or (
        ((user.first_name or "") + " " + (user.last_name or "")).strip() if user else ""
    ) or "Customer"
    customer_email = order.customer_email or (user.email if user else None)
    if not customer_email:
        return

    items = []
    for item in (order.items or []):
        items.append({
            "name": item.snapshot_name or (item.product.name if item.product else "Product"),
            "image": item.snapshot_image or (item.product.images[0].image_url if item.product and item.product.images else ""),
            "slug": item.snapshot_slug or (item.product.slug if item.product else ""),
        })

    await queue_email(
        db,
        recipient_email=customer_email,
        recipient_user_id=order.user_id,
        email_type="review_request",
        subject="How Was Your Purchase?",
        template_name="review_request.html",
        context={
            "customer_name": customer_name,
            "order_number": order.order_number,
            "items": items,
            "base_url": config.BASE_URL,
        },
        entity_type="Order",
        entity_id=order.id,
    )


async def send_newsletter_welcome_email(db: AsyncSession, email: str):
    """Send newsletter subscription confirmation."""
    await queue_email(
        db,
        recipient_email=email,
        email_type="newsletter",
        subject="You're Subscribed!",
        template_name="newsletter_welcome.html",
        context={
            "customer_name": "there",
            "unsubscribe_url": f"{config.BASE_URL}/api/newsletters/unsubscribe?email={email}",
        },
        entity_type=None,
        entity_id=None,
        skip_duplicate_check=True,
    )


async def send_admin_test_email(db: AsyncSession, to_email: str, email_type: str = "test"):
    """Send a test email from admin dashboard."""
    await queue_email(
        db,
        recipient_email=to_email,
        email_type="test",
        subject="Test Email – ASAH'S PRIMENEST",
        template_name="test_email.html",
        context={
            "customer_name": "Test User",
            "email_type": email_type,
            "sent_at": datetime.utcnow().strftime("%B %d, %Y at %I:%M %p"),
        },
        entity_type=None,
        entity_id=None,
        skip_duplicate_check=True,
    )


async def send_broadcast_email(
    db: AsyncSession,
    *,
    user,
    email_type: str,
    subject: str,
    title: str,
    message: Optional[str],
    campaign_id: int,
) -> Optional[EmailLog]:
    """Queue a broadcast announcement email for one customer.

    Respects the customer's email preferences via queue_email's preference
    gate (order updates / broadcast_order is always delivered).
    Returns the EmailLog, or None when skipped (opted out / SMTP unset).
    """
    customer_name = ((user.first_name or '') + ' ' + (user.last_name or '')).strip() or "there"
    return await queue_email(
        db,
        recipient_email=user.email,
        email_type=email_type,
        subject=subject or title,
        template_name="broadcast.html",
        context={
            "headline": title,
            "customer_name": customer_name,
            "content_html": message or "",
            "cta_url": f"{config.BASE_URL}/customer/dashboard",
            "cta_text": "View in Your Account",
            "unsubscribe_url": f"{config.BASE_URL}/customer/dashboard",
        },
        recipient_user_id=user.id,
        entity_type="campaign",
        entity_id=campaign_id,
        skip_duplicate_check=True,
    )
