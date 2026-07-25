"""Cart operations endpoint tests."""

import pytest
from httpx import AsyncClient

from app.models.catalog import Product, User


pytestmark = pytest.mark.asyncio


async def test_get_empty_cart(client: AsyncClient):
    resp = await client.get("/api/cart", params={"cart_id": "test-cart-001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["subtotal"] == 0.0
    assert data["item_count"] == 0


async def test_add_to_cart(client: AsyncClient, test_product: Product):
    payload = {"product_id": test_product.id, "quantity": 2}
    resp = await client.post(
        "/api/cart/items?cart_id=test-cart-add",
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == test_product.id
    assert data["items"][0]["quantity"] == 2
    assert data["item_count"] == 2


async def test_add_to_cart_nonexistent_product(client: AsyncClient):
    payload = {"product_id": 9999, "quantity": 1}
    resp = await client.post(
        "/api/cart/items?cart_id=test-cart-add-fail",
        json=payload,
    )
    assert resp.status_code == 404
    assert "Product not found" in resp.json()["detail"]


async def test_add_to_cart_insufficient_stock(client: AsyncClient, test_product: Product):
    payload = {"product_id": test_product.id, "quantity": 9999}
    resp = await client.post(
        "/api/cart/items?cart_id=test-cart-stock",
        json=payload,
    )
    assert resp.status_code == 400
    assert "Insufficient stock" in resp.json()["detail"]


async def test_add_multiple_items_to_cart(client: AsyncClient, test_product: Product):
    cart_id = "test-cart-multi"
    # Add item
    await client.post(
        "/api/cart/items",
        json={"product_id": test_product.id, "quantity": 1},
        params={"cart_id": cart_id},
    )
    # Add same item again (should update quantity)
    resp = await client.post(
        "/api/cart/items",
        json={"product_id": test_product.id, "quantity": 3},
        params={"cart_id": cart_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 3


async def test_update_cart_item(client: AsyncClient, test_product: Product):
    cart_id = "test-cart-update"
    # Add item
    await client.post(
        "/api/cart/items",
        json={"product_id": test_product.id, "quantity": 1},
        params={"cart_id": cart_id},
    )
    # Update quantity
    resp = await client.put(
        f"/api/cart/items/{test_product.id}",
        params={"cart_id": cart_id, "qty": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["quantity"] == 5


async def test_update_cart_item_not_in_cart(client: AsyncClient, test_product: Product):
    resp = await client.put(
        f"/api/cart/items/{test_product.id}",
        params={"cart_id": "empty-cart", "qty": 2},
    )
    assert resp.status_code == 404
    assert "Item not in cart" in resp.json()["detail"]


async def test_update_cart_item_invalid_qty(client: AsyncClient, test_product: Product):
    resp = await client.put(
        f"/api/cart/items/{test_product.id}",
        params={"cart_id": "test-cart-invalid", "qty": 0},
    )
    assert resp.status_code == 400
    assert "Quantity must be >= 1" in resp.json()["detail"]


async def test_remove_cart_item(client: AsyncClient, test_product: Product):
    cart_id = "test-cart-remove"
    # Add item
    await client.post(
        "/api/cart/items",
        json={"product_id": test_product.id, "quantity": 2},
        params={"cart_id": cart_id},
    )
    # Remove item
    resp = await client.delete(
        f"/api/cart/items/{test_product.id}",
        params={"cart_id": cart_id},
    )
    assert resp.status_code == 200
    assert "Item removed" in resp.json()["detail"]

    # Verify cart is empty
    get_resp = await client.get("/api/cart", params={"cart_id": cart_id})
    assert get_resp.json()["items"] == []


async def test_remove_nonexistent_cart_item(client: AsyncClient):
    resp = await client.delete(
        "/api/cart/items/9999",
        params={"cart_id": "test-cart-ghost"},
    )
    assert resp.status_code == 200
    assert "Item removed" in resp.json()["detail"]


async def test_clear_cart(client: AsyncClient, test_product: Product):
    cart_id = "test-cart-clear"
    # Add items
    await client.post(
        "/api/cart/items",
        json={"product_id": test_product.id, "quantity": 3},
        params={"cart_id": cart_id},
    )
    # Clear cart
    resp = await client.delete("/api/cart", params={"cart_id": cart_id})
    assert resp.status_code == 200
    assert "Cart cleared" in resp.json()["detail"]

    # Verify cart is empty
    get_resp = await client.get("/api/cart", params={"cart_id": cart_id})
    assert get_resp.json()["items"] == []
    assert get_resp.json()["subtotal"] == 0.0


async def test_cart_calculates_subtotal(client: AsyncClient, test_product: Product):
    cart_id = "test-cart-calc"
    resp = await client.post(
        "/api/cart/items",
        json={"product_id": test_product.id, "quantity": 3},
        params={"cart_id": cart_id},
    )
    data = resp.json()
    expected_subtotal = test_product.price * 3
    assert abs(data["subtotal"] - expected_subtotal) < 0.01
    assert data["item_count"] == 3
