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
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

    # PostgreSQL (async)
    DATABASE_URL = os.environ.get('DATABASE_URL') or \
        'postgresql+asyncpg://ecom_user:CHANGE_ME@localhost:5432/ecom_db'

    # Security — production must set these via environment variables
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-change-me'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'dev-jwt-secret-change-me'
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM') or 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES') or 60)

    # CORS — never default to wildcard
    CORS_ORIGINS = _csv_list(os.environ.get('CORS_ORIGINS')) or ['http://localhost:3000', 'http://localhost:8000']

    # Uploads
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'images', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Paystack
    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', '')
    PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
    PAYSTACK_WEBHOOK_SECRET = os.environ.get('PAYSTACK_WEBHOOK_SECRET', '')
    PAYSTACK_API_URL = 'https://api.paystack.co'

    # Base URL for callbacks
    BASE_URL = os.environ.get('BASE_URL', 'http://asahsprimenest.com')

    # Email / SMTP
    SMTP_HOST = os.environ.get('SMTP_HOST', '')
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
    EMAIL_FROM_NAME = os.environ.get('EMAIL_FROM_NAME', "ASAH'S PRIMENEST")
    EMAIL_FROM_ADDRESS = os.environ.get('EMAIL_FROM_ADDRESS', '')
    EMAIL_REPLY_TO = os.environ.get('EMAIL_REPLY_TO', '')


    # Arkesel SMS
    ARKESEL_API_KEY = os.environ.get('ARKESEL_API_KEY', '')
    ARKESEL_SENDER_ID = os.environ.get('ARKESEL_SENDER_ID', 'ASAHSPRIME')
    ADMIN_PHONE_NUMBER = os.environ.get('ADMIN_PHONE_NUMBER', '')


config = Config()
