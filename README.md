# ASAH'S PRIMENEST - E-Commerce API

A full-featured e-commerce platform built with **FastAPI**, **async SQLAlchemy 2.0**, and **PostgreSQL**. Designed for performance, scalability, and developer experience.

---

## Features

- **Product Catalog** - Products, categories, brands, collections with images, variants, and attributes
- **User Authentication** - JWT-based auth with bcrypt password hashing and role-based access control (RBAC)
- **Shopping Cart** - Session-based cart with add, update, remove, and clear operations
- **Order Management** - Full order lifecycle: checkout, status tracking, payment recording
- **Admin Dashboard** - Revenue stats, order management, inventory tracking, user management
- **Coupon System** - Percentage and fixed discounts with validation, expiry, and usage limits
- **Wishlist** - Save products for later
- **Blog** - CMS for blog posts with publish/draft workflow
- **Notifications** - Per-user notification system with read/unread states
- **Newsletter** - Email subscription management
- **Hero Banners** - Configurable homepage banners
- **Testimonials** - Customer review showcase
- **Audit Logging** - Full audit trail for admin actions
- **Media Library** - File upload and management
- **Inventory Management** - Warehouse-level stock tracking with reorder alerts
- **Search & Filtering** - Product search, category/brand/price filters, sorting
- **Rate Limiting** - Built-in request throttling middleware
- **Error Handling** - Global error handler middleware with structured responses

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.104+ |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 (asyncpg) |
| Auth | JWT (python-jose) + bcrypt |
| Validation | Pydantic v2 |
| Templates | Jinja2 |
| Testing | pytest + pytest-asyncio + httpx |
| Containerization | Docker + Docker Compose |
| Reverse Proxy | Nginx |

## Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Docker & Docker Compose (for containerized deployment)
- Node.js (optional, for frontend development)

## Installation

### Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd "E-Commerce 12"

# Copy environment file
cp .env.example .env

# Edit .env with your secrets
# At minimum, change SECRET_KEY and JWT_SECRET_KEY

# Start all services
docker-compose up -d

# The API is available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Local Development

```bash
# Clone and enter project
cd "E-Commerce 12"

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env

# Create the database
# Using psql: CREATE DATABASE ecom_db;
# Or let the app auto-create tables on startup

# Run the application
uvicorn manage:app --reload --host 0.0.0.0 --port 8000

# Seed sample data (optional)
python seed_comprehensive.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://ecom_user:ecom_secure_2026@localhost:5432/ecom_db` |
| `SECRET_KEY` | Application secret key | `dev-secret-change-me` |
| `JWT_SECRET_KEY` | JWT signing key | `dev-jwt-secret-change-me` |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL in minutes | `1440` (24h) |
| `CORS_ORIGINS` | Comma-separated allowed origins | `*` |
| `API_PREFIX` | API route prefix | `/api` |
| `PROJECT_NAME` | Application title | `ASAH'S PRIMENEST` |
| `DEBUG` | Enable debug mode | `True` |

## Database Setup

The application uses **async SQLAlchemy 2.0** with PostgreSQL. On first startup, all tables are automatically created via `Base.metadata.create_all`. For production, use **Alembic** migrations:

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Running the Application

```bash
# Development (with auto-reload)
uvicorn manage:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn manage:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once running, access the interactive API docs:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

For detailed endpoint reference, see [docs/API.md](docs/API.md).

## Default Credentials

After running `seed_comprehensive.py`:

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@primenest.com` | `admin123` |
| Customer | (register via UI or API) | - |

## Project Structure

```
E-Commerce 12/
├── app/
│   ├── api/                    # API route modules
│   │   ├── auth.py             # Registration, login, profile
│   │   ├── products.py         # Product CRUD + search
│   │   ├── categories.py       # Category CRUD
│   │   ├── brands.py           # Brand CRUD
│   │   ├── cart.py             # Shopping cart
│   │   ├── orders.py           # Checkout + order management
│   │   ├── customers.py        # Customer profiles + addresses
│   │   ├── admin.py            # Admin dashboard + management
│   │   ├── coupons.py          # Coupon CRUD + validation
│   │   ├── wishlists.py        # Wishlist operations
│   │   ├── blog.py             # Blog post management
│   │   ├── newsletters.py      # Newsletter subscriptions
│   │   ├── notifications.py    # User notifications
│   │   ├── collections.py      # Product collections
│   │   ├── testimonials.py     # Customer testimonials
│   │   ├── hero_banners.py     # Homepage banners
│   │   ├── audit.py            # Audit + system logs
│   │   └── content.py          # Homepage content API
│   ├── models/
│   │   └── catalog.py          # All SQLAlchemy models
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── security.py             # JWT + password hashing + dependencies
│   ├── db.py                   # Async engine + session factory
│   ├── audit.py                # Audit logging utilities
│   ├── middleware/
│   │   ├── rate_limit.py       # Rate limiting middleware
│   │   └── error_handler.py    # Global error handler
│   ├── services/               # Business logic services
│   ├── templates/              # Jinja2 HTML templates
│   └── static/                 # CSS, JS, images
├── backend/
│   ├── Dockerfile              # Multi-stage Docker build
│   └── tests/                  # Test suite
│       ├── conftest.py         # Fixtures + test DB setup
│       ├── test_auth.py        # Authentication tests
│       ├── test_products.py    # Product CRUD tests
│       ├── test_categories.py  # Category CRUD tests
│       ├── test_orders.py      # Order lifecycle tests
│       ├── test_cart.py        # Cart operation tests
│       └── test_admin.py       # Admin endpoint tests
├── docs/
│   ├── API.md                  # API endpoint reference
│   └── DEPLOYMENT.md           # Production deployment guide
├── nginx/
│   └── nginx.conf              # Nginx reverse proxy config
├── migrations/                 # Alembic database migrations
├── config.py                   # Application configuration
├── manage.py                   # App entry point
├── docker-compose.yml          # Docker Compose services
├── requirements.txt            # Python dependencies
├── seed.py                     # Basic data seeder
├── seed_comprehensive.py       # Full data seeder
└── README.md                   # This file
```

## Testing

```bash
# Install test dependencies (included in requirements.txt)
pip install pytest pytest-asyncio httpx aiosqlite

# Run all tests
cd backend
pytest tests/ -v

# Run specific test file
pytest tests/test_auth.py -v

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=app --cov-report=term-missing
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest tests/ -v`)
6. Run linting (`ruff check .` and `ruff format .`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

### Code Style

- Follow PEP 8 conventions
- Use type hints for all function signatures
- Keep functions focused and small
- Write docstrings for public functions
- Use Pydantic models for all request/response data

## License

This project is proprietary software. All rights reserved.
