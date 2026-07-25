"""Paystack payment gateway service.

Provides server-side transaction initialization, verification, and webhook
signature validation. All Paystack API calls go through httpx with the
secret key stored only in environment variables.
"""

import hashlib
import hmac
import json
from typing import Optional

import httpx
from config import config


class PaystackService:
    """Paystack API client."""

    def __init__(self):
        self.secret_key = config.PAYSTACK_SECRET_KEY
        self.api_url = config.PAYSTACK_API_URL
        self.webhook_secret = config.PAYSTACK_WEBHOOK_SECRET
        self.base_url = config.BASE_URL

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    async def initialize_transaction(
        self,
        email: str,
        amount_kobo: int,
        reference: str,
        order_id: int,
        order_number: str,
        currency: str = "GHS",
        callback_url: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Initialize a Paystack transaction.

        Args:
            email: Customer email address
            amount_kobo: Amount in kobo/pesewas (amount * 100)
            reference: Unique transaction reference
            order_id: Internal order ID
            order_number: Human-readable order number
            currency: Currency code (GHS for Ghana)
            callback_url: URL to redirect after payment
            metadata: Extra metadata to pass to Paystack

        Returns:
            dict with keys: status, message, data (contains authorization_url, access_code, reference)
        """
        if not self.secret_key:
            return {"status": False, "message": "Paystack secret key not configured"}

        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "currency": currency,
            "callback_url": callback_url or f"{self.base_url}/payment/callback",
            "metadata": {
                "order_id": order_id,
                "order_number": order_number,
                "cancel_action": f"{self.base_url}/payment/failed?order_id={order_id}",
                **(metadata or {}),
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.api_url}/transaction/initialize",
                    json=payload,
                    headers=self.headers,
                )
                data = response.json()
                return data
            except httpx.HTTPError as e:
                return {"status": False, "message": f"HTTP error: {str(e)}"}
            except Exception as e:
                return {"status": False, "message": f"Error: {str(e)}"}

    async def verify_transaction(self, reference: str) -> dict:
        """Verify a Paystack transaction by reference.

        Returns:
            dict with verification result including status, amount, currency, etc.
        """
        if not self.secret_key:
            return {"status": False, "message": "Paystack secret key not configured"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.api_url}/transaction/verify/{reference}",
                    headers=self.headers,
                )
                data = response.json()
                return data
            except httpx.HTTPError as e:
                return {"status": False, "message": f"HTTP error: {str(e)}"}
            except Exception as e:
                return {"status": False, "message": f"Error: {str(e)}"}

    def verify_webhook_signature(self, payload_body: bytes, signature: str) -> bool:
        """Verify the webhook signature sent by Paystack.

        Paystack signs the webhook body with HMAC SHA512 using the webhook secret.
        """
        if not self.webhook_secret:
            return False

        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload_body,
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    @staticmethod
    def amount_to_kobo(amount: float) -> int:
        """Convert amount to kobo/pesewas (multiply by 100)."""
        return int(round(amount * 100))

    @staticmethod
    def kobo_to_amount(kobo: int) -> float:
        """Convert kobo/pesewas back to amount (divide by 100)."""
        return round(kobo / 100, 2)


# Singleton
paystack = PaystackService()
