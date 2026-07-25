import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def _csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(',') if v.strip()]


class Config:
    PROJECT_NAME = os.environ.get('PROJECT_NAME') or "E-Commerce API"
    API_PREFIX = os.environ.get('API_PREFIX') or '/api'
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

    # PostgreSQL (async) — SQLite fallback only for local dev
    DATABASE_URL = os.environ.get('DATABASE_URL') or \
        'postgresql+asyncpg://ecom_user:ecom_secure_2026@localhost:5432/ecom_db'

    # Security — never use defaults in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-change-me'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'dev-jwt-secret-change-me'
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM') or 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES') or 1440)

    # CORS
    CORS_ORIGINS = _csv_list(os.environ.get('CORS_ORIGINS')) or ['*']

    # Uploads
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'images', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB


config = Config()
