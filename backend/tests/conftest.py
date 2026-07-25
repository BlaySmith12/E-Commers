"""Shared test fixtures for the e-commerce API test suite."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.models.catalog import (
    Category,
    Permission,
    Product,
    ProductImage,
    Role,
    User,
)
from app.security import create_access_token, hash_password
from app.web import create_app

# ---------------------------------------------------------------------------
# SQLite async engine for tests
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Event-loop fixture (session scope)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database setup / teardown
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Override DB dependency
# ---------------------------------------------------------------------------
async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# FastAPI test app
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
async def _create_role(
    db: AsyncSession,
    name: str,
    permissions: int,
    default: bool = False,
) -> Role:
    role = Role(name=name, permissions=permissions, default=default)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def _create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str = "testpass123",
    role: Role | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        email=email,
        first_name=username.title(),
        last_name="Test",
        phone="+1234567890",
        is_active=is_active,
        role=role,
    )
    user.password = password
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_category(db: AsyncSession, name: str, slug: str) -> Category:
    cat = Category(name=name, slug=slug, description=f"{name} category")
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def _create_product(
    db: AsyncSession,
    name: str,
    sku: str,
    slug: str,
    price: float = 29.99,
    stock: int = 50,
    category_id: int | None = None,
) -> Product:
    product = Product(
        name=name,
        sku=sku,
        slug=slug,
        price=price,
        stock=stock,
        status="active",
        description=f"Description for {name}",
        category_id=category_id,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


# ---------------------------------------------------------------------------
# Fixture: default user role + admin role (created per test)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def default_role(db_session: AsyncSession) -> Role:
    return await _create_role(db_session, "Customer", Permission.VIEW, default=True)


@pytest_asyncio.fixture
async def admin_role(db_session: AsyncSession) -> Role:
    return await _create_role(db_session, "Admin", Permission.ALL)


@pytest_asyncio.fixture
async def editor_role(db_session: AsyncSession) -> Role:
    return await _create_role(db_session, "Editor", Permission.VIEW | Permission.CREATE | Permission.EDIT)


@pytest_asyncio.fixture
async def viewer_role(db_session: AsyncSession) -> Role:
    return await _create_role(db_session, "Viewer", Permission.VIEW)


# ---------------------------------------------------------------------------
# Fixture: test users
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, default_role: Role) -> User:
    return await _create_user(db_session, "testuser", "test@example.com", "testpass123", default_role)


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, admin_role: Role) -> User:
    return await _create_user(db_session, "adminuser", "admin@example.com", "adminpass123", admin_role)


@pytest_asyncio.fixture
async def editor_user(db_session: AsyncSession, editor_role: Role) -> User:
    return await _create_user(db_session, "editoruser", "editor@example.com", "editorpass123", editor_role)


# ---------------------------------------------------------------------------
# Fixture: auth headers
# ---------------------------------------------------------------------------
@pytest.fixture
def user_headers(test_user: User) -> dict:
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    token = create_access_token(subject=admin_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def editor_headers(editor_user: User) -> dict:
    token = create_access_token(subject=editor_user.id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixture: test category & product
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_category(db_session: AsyncSession) -> Category:
    return await _create_category(db_session, "Electronics", "electronics")


@pytest_asyncio.fixture
async def test_product(db_session: AsyncSession, test_category: Category) -> Product:
    return await _create_product(
        db_session,
        name="Test Phone",
        sku="PHONE-001",
        slug="test-phone",
        price=599.99,
        stock=100,
        category_id=test_category.id,
    )
