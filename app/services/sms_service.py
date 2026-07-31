import logging

import httpx
from sqlalchemy import select

from config import config
from app.db import async_session_maker
from app.models.catalog import SiteSetting

logger = logging.getLogger(__name__)

ARKESEL_API_URL = "https://sms.arkesel.com/api/v2/sms/send"


async def _get_sms_config():
    api_key = config.ARKESEL_API_KEY
    sender_id = config.ARKESEL_SENDER_ID
    admin_phone = config.ADMIN_PHONE_NUMBER

    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(SiteSetting).where(
                    SiteSetting.key.in_(["arkesel_api_key", "arkesel_sender_id", "admin_sms_phone"])
                )
            )
            for row in result.scalars().all():
                if row.key == "arkesel_api_key" and row.value:
                    api_key = row.value
                elif row.key == "arkesel_sender_id" and row.value:
                    sender_id = row.value
                elif row.key == "admin_sms_phone" and row.value:
                    admin_phone = row.value
    except Exception:
        logger.exception("Failed to read SMS settings from DB")

    return api_key, sender_id, admin_phone


async def send_admin_sms_message(message: str) -> bool:
    """Send an SMS notification to the admin with an arbitrary message."""
    api_key, sender_id, admin_phone = await _get_sms_config()

    if not api_key or not admin_phone:
        logger.warning("Arkesel SMS not configured – skipping admin SMS: %.80s", message)
        return False

    if sender_id and len(sender_id) > 11:
        sender_id = sender_id[:11]

    payload = {
        "sender": sender_id or "ASAHSPRIME",
        "message": message[:160],
        "recipients": [admin_phone],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                ARKESEL_API_URL,
                json=payload,
                headers={"Content-Type": "application/json", "api-key": api_key},
            )
            data = resp.json()
            if resp.is_error:
                logger.error(
                    "Arkesel API error: status=%s body=%s",
                    resp.status_code, data,
                )
                return False
            logger.info("Admin SMS sent – Arkesel response: %s", data)
            return True
    except Exception:
        logger.exception("Failed to send admin SMS")
        return False


async def send_admin_sms(order) -> bool:
    """Send an SMS notification to the admin when a new order is placed."""
    customer_name = order.customer_name or f"User #{order.user_id}"
    payment_status = getattr(order, 'payment_status', 'Pending')
    message = f"New Order #{order.order_number} | {customer_name} | GHS {order.total_amount:.2f} | {payment_status}"
    return await send_admin_sms_message(message)
