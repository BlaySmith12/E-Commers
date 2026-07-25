"""Authentication endpoint tests."""

import pytest
from httpx import AsyncClient

from app.models.catalog import User
from app.db import get_db


pytestmark = pytest.mark.asyncio


async def test_register_success(client: AsyncClient):
    payload = {
        "username": "newuser",
        "email": "new@example.com",
        "password": "securepass123",
        "first_name": "New",
        "last_name": "User",
    }
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["username"] == "newuser"


async def test_register_duplicate_email(client: AsyncClient, test_user: User):
    payload = {
        "username": "anotheruser",
        "email": "test@example.com",
        "password": "securepass123",
    }
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400
    assert "Email already registered" in resp.json()["detail"]


async def test_register_duplicate_username(client: AsyncClient, test_user: User):
    payload = {
        "username": "testuser",
        "email": "unique@example.com",
        "password": "securepass123",
    }
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400
    assert "Username already taken" in resp.json()["detail"]


async def test_login_success(client: AsyncClient, test_user: User):
    payload = {
        "username": "test@example.com",
        "password": "testpass123",
    }
    resp = await client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == "testuser"


async def test_login_with_username(client: AsyncClient, test_user: User):
    payload = {
        "username": "testuser",
        "password": "testpass123",
    }
    resp = await client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "test@example.com"


async def test_login_wrong_password(client: AsyncClient, test_user: User):
    payload = {
        "username": "test@example.com",
        "password": "wrongpassword",
    }
    resp = await client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


async def test_login_nonexistent_user(client: AsyncClient):
    payload = {
        "username": "nonexistent@example.com",
        "password": "whatever123",
    }
    resp = await client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


async def test_get_me(client: AsyncClient, user_headers: dict):
    resp = await client.get("/api/auth/me", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert data["is_active"] is True


async def test_get_me_unauthorized(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_get_me_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert resp.status_code == 401


async def test_logout(client: AsyncClient, user_headers: dict):
    resp = await client.post("/api/auth/logout", headers=user_headers)
    assert resp.status_code == 200
    assert "Logged out" in resp.json()["detail"]
