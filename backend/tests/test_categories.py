"""Category CRUD endpoint tests."""

import pytest
from httpx import AsyncClient

from app.models.catalog import Category, User


pytestmark = pytest.mark.asyncio


async def test_list_categories(client: AsyncClient, test_category: Category):
    resp = await client.get("/api/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    names = [c["name"] for c in data]
    assert "Electronics" in names


async def test_list_categories_empty(client: AsyncClient):
    resp = await client.get("/api/categories")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_category(client: AsyncClient, test_category: Category):
    resp = await client.get(f"/api/categories/{test_category.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Electronics"
    assert data["slug"] == "electronics"


async def test_get_category_not_found(client: AsyncClient):
    resp = await client.get("/api/categories/9999")
    assert resp.status_code == 404


async def test_create_category_admin(client: AsyncClient, admin_headers: dict):
    payload = {
        "name": "Clothing",
        "slug": "clothing",
        "description": "Fashion and apparel",
    }
    resp = await client.post("/api/categories", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Clothing"
    assert data["slug"] == "clothing"


async def test_create_category_duplicate_slug(
    client: AsyncClient, admin_headers: dict, test_category: Category
):
    payload = {"name": "Duplicate", "slug": "electronics"}
    resp = await client.post("/api/categories", json=payload, headers=admin_headers)
    assert resp.status_code == 400
    assert "Slug already exists" in resp.json()["detail"]


async def test_create_category_unauthorized(client: AsyncClient):
    payload = {"name": "Nope", "slug": "nope"}
    resp = await client.post("/api/categories", json=payload)
    assert resp.status_code == 401


async def test_create_category_normal_user_forbidden(
    client: AsyncClient, user_headers: dict
):
    payload = {"name": "Forbidden", "slug": "forbidden"}
    resp = await client.post("/api/categories", json=payload, headers=user_headers)
    assert resp.status_code == 403


async def test_update_category_admin(
    client: AsyncClient, admin_headers: dict, test_category: Category
):
    payload = {"name": "Consumer Electronics"}
    resp = await client.put(
        f"/api/categories/{test_category.id}", json=payload, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Consumer Electronics"


async def test_update_category_not_found(client: AsyncClient, admin_headers: dict):
    payload = {"name": "Ghost"}
    resp = await client.put("/api/categories/9999", json=payload, headers=admin_headers)
    assert resp.status_code == 404


async def test_delete_category_admin(
    client: AsyncClient, admin_headers: dict, test_category: Category
):
    resp = await client.delete(
        f"/api/categories/{test_category.id}", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "Category deleted" in resp.json()["detail"]
    # Verify gone
    resp2 = await client.get(f"/api/categories/{test_category.id}")
    assert resp2.status_code == 404


async def test_delete_category_not_found(client: AsyncClient, admin_headers: dict):
    resp = await client.delete("/api/categories/9999", headers=admin_headers)
    assert resp.status_code == 404
