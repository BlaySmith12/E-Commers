"""Admin-only endpoint tests."""

import pytest
from httpx import AsyncClient

from app.models.catalog import Category, Product, User


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
async def test_admin_dashboard(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/admin/dashboard", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "revenue_today" in data
    assert "revenue_month" in data
    assert "orders_today" in data
    assert "orders_month" in data
    assert "product_count" in data
    assert "customer_count" in data
    assert "pending_orders" in data
    assert "low_stock_alerts" in data


async def test_admin_dashboard_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/dashboard")
    assert resp.status_code == 401


async def test_admin_dashboard_normal_user_forbidden(
    client: AsyncClient, user_headers: dict
):
    resp = await client.get("/api/admin/dashboard", headers=user_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
async def test_admin_list_users(client: AsyncClient, admin_headers: dict, test_user: User):
    resp = await client.get("/api/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    usernames = [u["username"] for u in data]
    assert "testuser" in usernames


async def test_admin_list_users_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


async def test_admin_list_customers(client: AsyncClient, admin_headers: dict, test_user: User):
    resp = await client.get("/api/admin/customers", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_admin_update_user_role(
    client: AsyncClient, admin_headers: dict, test_user: User, editor_role
):
    resp = await client.patch(
        f"/api/admin/users/{test_user.id}/role",
        json={"role_id": editor_role.id},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role_id"] == editor_role.id


# ---------------------------------------------------------------------------
# Category management (admin routes)
# ---------------------------------------------------------------------------
async def test_admin_categories_crud(client: AsyncClient, admin_headers: dict):
    # Create
    create_resp = await client.post(
        "/api/admin/categories",
        json={"name": "Admin Cat", "slug": "admin-cat"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    cat_id = create_resp.json()["id"]

    # List
    list_resp = await client.get("/api/admin/categories", headers=admin_headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == cat_id for c in list_resp.json())

    # Update
    update_resp = await client.put(
        f"/api/admin/categories/{cat_id}",
        json={"name": "Updated Admin Cat"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Admin Cat"

    # Delete
    del_resp = await client.delete(
        f"/api/admin/categories/{cat_id}", headers=admin_headers
    )
    assert del_resp.status_code == 200
    assert "deleted" in del_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Product management (admin routes)
# ---------------------------------------------------------------------------
async def test_admin_product_crud(client: AsyncClient, admin_headers: dict):
    # Create product
    create_resp = await client.post(
        "/api/admin/products",
        json={
            "name": "Admin Product",
            "sku": "ADMIN-SKU-001",
            "slug": "admin-product",
            "price": 99.99,
            "stock": 10,
            "status": "active",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    product_id = create_resp.json()["id"]

    # List products
    list_resp = await client.get("/api/admin/products", headers=admin_headers)
    assert list_resp.status_code == 200
    assert any(p["id"] == product_id for p in list_resp.json())

    # Update product
    update_resp = await client.put(
        f"/api/admin/products/{product_id}",
        json={"name": "Updated Admin Product", "price": 149.99},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Admin Product"
    assert update_resp.json()["price"] == 149.99

    # Delete product
    del_resp = await client.delete(
        f"/api/admin/products/{product_id}", headers=admin_headers
    )
    assert del_resp.status_code == 200


# ---------------------------------------------------------------------------
# Brand management (admin routes)
# ---------------------------------------------------------------------------
async def test_admin_brand_crud(client: AsyncClient, admin_headers: dict):
    create_resp = await client.post(
        "/api/admin/brands",
        json={"name": "Admin Brand", "slug": "admin-brand"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    brand_id = create_resp.json()["id"]

    list_resp = await client.get("/api/admin/brands", headers=admin_headers)
    assert list_resp.status_code == 200

    update_resp = await client.put(
        f"/api/admin/brands/{brand_id}",
        json={"name": "Updated Brand"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Brand"

    del_resp = await client.delete(
        f"/api/admin/brands/{brand_id}", headers=admin_headers
    )
    assert del_resp.status_code == 200


# ---------------------------------------------------------------------------
# Unauthorized access tests
# ---------------------------------------------------------------------------
async def test_unauthorized_admin_access(client: AsyncClient):
    """All admin endpoints return 401 without a token."""
    endpoints = [
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/customers"),
        ("GET", "/api/admin/categories"),
        ("GET", "/api/admin/products"),
        ("GET", "/api/admin/brands"),
        ("GET", "/api/admin/settings"),
        ("GET", "/api/admin/reviews"),
        ("GET", "/api/admin/inventory"),
        ("GET", "/api/admin/payments"),
    ]
    for method, url in endpoints:
        resp = await client.request(method, url)
        assert resp.status_code == 401, f"{method} {url} should return 401"


async def test_normal_user_forbidden_admin_endpoints(
    client: AsyncClient, user_headers: dict
):
    """Normal users get 403 on admin endpoints."""
    endpoints = [
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/customers"),
        ("GET", "/api/admin/categories"),
        ("GET", "/api/admin/products"),
        ("GET", "/api/admin/brands"),
    ]
    for method, url in endpoints:
        resp = await client.request(method, url, headers=user_headers)
        assert resp.status_code == 403, f"{method} {url} should return 403 for normal user"
