import logging

import httpx

from config import config
from app.settings_cache import get_cached_settings

logger = logging.getLogger(__name__)

ARKESEL_API_URL = "https://sms.arkesel.com/api/v2/sms/send"


def _get_sms_config():
    settings = get_cached_settings()
    api_key = settings.get("arkesel_api_key") or config.ARKESEL_API_KEY
    sender_id = settings.get("arkesel_sender_id") or config.ARKESEL_SENDER_ID
    admin_phone = settings.get("admin_sms_phone") or config.ADMIN_PHONE_NUMBER
    return api_key, sender_id, admin_phone


async def send_admin_sms(order) -> bool:
    """Send an SMS notification to the admin when a new order is placed."""
    api_key, sender_id, admin_phone = _get_sms_config()

    if not api_key or not admin_phone:
        logger.debug("Arkesel SMS not configured – skipping admin SMS")
        return False

    customer_name = order.customer_name or f"User #{order.user_id}"
    items_summary = ", ".join(
        (i.snapshot_name or f"Product #{i.product_id}")
        for i in (order.items or [])
    ) or "N/A"

    message = (
        f"New Order #{order.order_number}\n"
        f"Customer: {customer_name}\n"
        f"Total: GHS {order.total_amount:.2f}\n"
        f"Payment: {getattr(order, 'payment_status', 'Pending')}\n"
        f"Items: {items_summary}"
    )

    payload = {
        "sender": sender_id or "ASAHSPRIME",
        "message": message,
        "recipients": [admin_phone],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                ARKESEL_API_URL,
                json=payload,
                headers={"api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info("Admin SMS sent for order #%s – Arkesel response: %s", order.order_number, data)
            return True
    except Exception:
        logger.exception("Failed to send admin SMS for order #%s", order.order_number)
        return False
