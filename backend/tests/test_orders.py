"""Order lifecycle endpoint tests."""

import pytest
from httpx import AsyncClient

from app.models.catalog import Category, Order, Product, User, Address


pytestmark = pytest.mark.asyncio


async def _create_address(client: AsyncClient, user_headers: dict) -> int:
    payload = {
        "street": "123 Test Street",
        "city": "Accra",
        "state": "Greater Accra",
        "country": "Ghana",
        "zip_code": "00233",
        "is_default": True,
    }
    resp = await client.post(
        "/api/customers/me/addresses", json=payload, headers=user_headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_list_orders_empty(client: AsyncClient, user_headers: dict):
    resp = await client.get("/api/orders", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_checkout(client: AsyncClient, user_headers: dict, test_product: Product):
    address_id = await _create_address(client, user_headers)
    payload = {
        "address_id": address_id,
        "payment_method": "Cash on Delivery",
        "shipping_fee": 5.0,
        "tax": 2.0,
    }
    resp = await client.post(
        "/api/orders/checkout?cart_id=test-cart-123",
        json=payload,
        headers=user_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "Pending"
    assert "order_number" in data
    assert data["shipping_fee"] == 5.0


async def test_checkout_inline_address(client: AsyncClient, user_headers: dict, test_product: Product):
    payload = {
        "street": "456 Inline Ave",
        "city": "Kumasi",
        "state": "Ashanti",
        "country": "Ghana",
        "payment_method": "Cash on Delivery",
        "shipping_fee": 3.0,
        "tax": 1.0,
    }
    resp = await client.post(
        "/api/orders/checkout?cart_id=test-cart-inline",
        json=payload,
        headers=user_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "Pending"


async def test_checkout_no_address(client: AsyncClient, user_headers: dict):
    payload = {"payment_method": "Cash on Delivery"}
    resp = await client.post(
        "/api/orders/checkout?cart_id=test-cart-noaddr",
        json=payload,
        headers=user_headers,
    )
    assert resp.status_code == 400
    assert "Address required" in resp.json()["detail"]


async def test_list_orders_after_checkout(
    client: AsyncClient, user_headers: dict, test_product: Product
):
    address_id = await _create_address(client, user_headers)
    checkout_payload = {
        "address_id": address_id,
        "payment_method": "Cash on Delivery",
    }
    await client.post(
        "/api/orders/checkout?cart_id=test-cart-list",
        json=checkout_payload,
        headers=user_headers,
    )
    resp = await client.get("/api/orders", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


async def test_get_order(
    client: AsyncClient, user_headers: dict, test_product: Product
):
    address_id = await _create_address(client, user_headers)
    checkout_resp = await client.post(
        "/api/orders/checkout?cart_id=test-cart-get",
        json={"address_id": address_id},
        headers=user_headers,
    )
    order_id = checkout_resp.json()["id"]
    resp = await client.get(f"/api/orders/{order_id}", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == order_id


async def test_get_order_not_found(client: AsyncClient, user_headers: dict):
    resp = await client.get("/api/orders/9999", headers=user_headers)
    assert resp.status_code == 404


async def test_update_order_status(
    client: AsyncClient,
    admin_headers: dict,
    editor_headers: dict,
    test_product: Product,
):
    # Create order as normal user
    address_payload = {
        "street": "789 Admin St",
        "city": "Tema",
        "country": "Ghana",
    }
    addr_resp = await client.post(
        "/api/customers/me/addresses",
        json=address_payload,
        headers={
            "Authorization": f"Bearer {pytest.__dict__.get('_test_token', '')}"
        },
    )
    # Use the test user headers for checkout
    from app.security import create_access_token

    from tests.conftest import TestSessionLocal
    from app.models.catalog import User, Role, Permission

    async with TestSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(User).where(User.username == "testuser")
        )
        user = result.scalar_one_or_none()
        if user:
            user_token = create_access_token(subject=user.id)
        else:
            pytest.skip("test user not found")

    user_h = {"Authorization": f"Bearer {user_token}"}

    addr_resp = await client.post(
        "/api/customers/me/addresses",
        json={"street": "789 Order St", "city": "Tema", "country": "Ghana"},
        headers=user_h,
    )
    address_id = addr_resp.json()["id"]

    checkout_resp = await client.post(
        "/api/orders/checkout?cart_id=test-cart-status",
        json={"address_id": address_id},
        headers=user_h,
    )
    order_id = checkout_resp.json()["id"]

    # Update status with editor
    resp = await client.patch(
        f"/api/orders/{order_id}/status",
        json={"status": "Processing"},
        headers=editor_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Processing"


async def test_update_order_status_not_found(client: AsyncClient, admin_headers: dict):
    resp = await client.patch(
        "/api/orders/9999/status",
        json={"status": "Shipped"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
