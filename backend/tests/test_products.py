"""Product CRUD endpoint tests."""

import pytest
from httpx import AsyncClient

from app.models.catalog import Category, Product, User
from app.db import get_db


pytestmark = pytest.mark.asyncio


async def test_list_products(client: AsyncClient, test_product: Product):
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "Test Phone"


async def test_list_products_empty(client: AsyncClient):
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_products_with_category_filter(
    client: AsyncClient, test_product: Product, test_category: Category
):
    resp = await client.get(f"/api/products?category_id={test_category.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(p["category_id"] == test_category.id for p in data)


async def test_list_products_with_price_filter(client: AsyncClient, test_product: Product):
    resp = await client.get("/api/products?min_price=100&max_price=1000")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_list_products_with_search(client: AsyncClient, test_product: Product):
    resp = await client.get("/api/products?search=Phone")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_list_products_out_of_price_range(client: AsyncClient, test_product: Product):
    resp = await client.get("/api/products?min_price=9999")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_product(client: AsyncClient, test_product: Product):
    resp = await client.get(f"/api/products/{test_product.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Phone"
    assert data["sku"] == "PHONE-001"
    assert data["price"] == 599.99
    assert data["stock"] == 100


async def test_get_product_by_slug(client: AsyncClient, test_product: Product):
    resp = await client.get("/api/products/slug/test-phone")
    assert resp.status_code == 200
    assert resp.json()["id"] == test_product.id


async def test_get_product_not_found(client: AsyncClient):
    resp = await client.get("/api/products/9999")
    assert resp.status_code == 404
    assert "Product not found" in resp.json()["detail"]


async def test_create_product_admin(client: AsyncClient, admin_headers: dict):
    payload = {
        "name": "New Laptop",
        "sku": "LAPTOP-001",
        "slug": "new-laptop",
        "price": 1299.99,
        "stock": 25,
        "description": "A powerful laptop",
        "is_featured": True,
        "status": "active",
    }
    resp = await client.post("/api/products", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Laptop"
    assert data["sku"] == "LAPTOP-001"
    assert data["price"] == 1299.99


async def test_create_product_unauthorized(client: AsyncClient):
    payload = {
        "name": "Unauthorized Product",
        "sku": "UNAUTH-001",
        "slug": "unauthorized-product",
        "price": 10.0,
        "stock": 1,
    }
    resp = await client.post("/api/products", json=payload)
    assert resp.status_code == 401


async def test_create_product_normal_user_forbidden(
    client: AsyncClient, user_headers: dict
):
    payload = {
        "name": "Forbidden Product",
        "sku": "FORBID-001",
        "slug": "forbidden-product",
        "price": 10.0,
        "stock": 1,
    }
    resp = await client.post("/api/products", json=payload, headers=user_headers)
    assert resp.status_code == 403


async def test_create_product_duplicate_sku(
    client: AsyncClient, admin_headers: dict, test_product: Product
):
    payload = {
        "name": "Duplicate SKU",
        "sku": "PHONE-001",
        "slug": "duplicate-sku",
        "price": 10.0,
        "stock": 1,
    }
    resp = await client.post("/api/products", json=payload, headers=admin_headers)
    assert resp.status_code == 400
    assert "SKU already exists" in resp.json()["detail"]


async def test_update_product_admin(
    client: AsyncClient, admin_headers: dict, test_product: Product
):
    payload = {"name": "Updated Phone", "price": 499.99}
    resp = await client.put(
        f"/api/products/{test_product.id}", json=payload, headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Phone"
    assert data["price"] == 499.99
    assert data["stock"] == 100


async def test_update_product_not_found(client: AsyncClient, admin_headers: dict):
    payload = {"name": "Ghost"}
    resp = await client.put("/api/products/9999", json=payload, headers=admin_headers)
    assert resp.status_code == 404


async def test_delete_product_admin(
    client: AsyncClient, admin_headers: dict, test_product: Product
):
    resp = await client.delete(
        f"/api/products/{test_product.id}", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "Product deleted" in resp.json()["detail"]
    # Verify gone
    resp2 = await client.get(f"/api/products/{test_product.id}")
    assert resp2.status_code == 404


async def test_delete_product_not_found(client: AsyncClient, admin_headers: dict):
    resp = await client.delete("/api/products/9999", headers=admin_headers)
    assert resp.status_code == 404


async def test_count_products(client: AsyncClient, test_product: Product):
    resp = await client.get("/api/products/count")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
