# Production Deployment Guide

This guide covers deploying ASAH'S PRIMENEST to production using Docker or manual setup.

---

## Table of Contents

- [Docker Deployment](#docker-deployment)
- [Manual Deployment](#manual-deployment)
- [Nginx Configuration](#nginx-configuration)
- [SSL/TLS Setup](#ssltls-setup)
- [Database Migration](#database-migration)
- [Environment Variables](#environment-variables)
- [Monitoring](#monitoring)
- [Backup Strategy](#backup-strategy)
- [Troubleshooting](#troubleshooting)

---

## Docker Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- A server with at least 2GB RAM

### Steps

1. **Clone and configure**
```bash
git clone <repository-url>
cd "E-Commerce 12"
cp .env.example .env
```

2. **Edit `.env` for production**
```bash
# Generate secure keys
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Update .env with these values
DEBUG=False
CORS_ORIGINS=https://yourdomain.com
```

3. **Start services**
```bash
docker-compose up -d --build
```

4. **Run initial migration**
```bash
docker-compose exec app alembic upgrade head
```

5. **Seed admin user**
```bash
docker-compose exec app python seed_comprehensive.py
```

6. **Verify**
```bash
curl http://localhost:8000/health
# Should return: {"status": "ok"}
```

### Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| `postgres` | 5432 | PostgreSQL 16 database |
| `app` | 8000 | FastAPI application |
| `nginx` | 80/443 | Reverse proxy |

### Managing Services

```bash
# View logs
docker-compose logs -f app
docker-compose logs -f postgres

# Restart a service
docker-compose restart app

# Stop all services
docker-compose down

# Stop and remove volumes (CAUTION: destroys data)
docker-compose down -v
```

---

## Manual Deployment

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Nginx (for reverse proxy)
- Supervisor or systemd (for process management)

### Steps

1. **Install system dependencies**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip postgresql libpq-dev nginx certbot python3-certbot-nginx

# CentOS/RHEL
sudo dnf install python3.11 python3.11-devel postgresql-server nginx
```

2. **Create database user and database**
```bash
sudo -u postgres psql
CREATE USER ecom_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE ecom_db OWNER ecom_user;
GRANT ALL PRIVILEGES ON DATABASE ecom_db TO ecom_user;
\q
```

3. **Set up application**
```bash
sudo mkdir -p /var/www/ecommerce
sudo chown $USER:$USER /var/www/ecommerce
cd /var/www/ecommerce

git clone <repository-url> .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with production values
```

4. **Create systemd service**
```bash
sudo cat > /etc/systemd/system/ecommerce.service << 'EOF'
[Unit]
Description=ASAH'S PRIMENEST E-Commerce API
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/ecommerce
Environment="PATH=/var/www/ecommerce/venv/bin"
ExecStart=/var/www/ecommerce/venv/bin/uvicorn manage:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ecommerce
sudo systemctl start ecommerce
```

5. **Run migrations**
```bash
cd /var/www/ecommerce
source venv/bin/activate
alembic upgrade head
python seed_comprehensive.py
```

6. **Configure Nginx** (see next section)

---

## Nginx Configuration

### Basic Reverse Proxy

```nginx
upstream ecommerce_app {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 16M;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL configuration (see SSL/TLS section)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 16M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;

    # Static files
    location /static/ {
        alias /var/www/ecommerce/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api/ {
        proxy_pass http://ecommerce_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        proxy_pass http://ecommerce_app;
        proxy_set_header Host $host;
    }

    # Swagger docs (restrict to admin IPs in production)
    location /docs {
        proxy_pass http://ecommerce_app;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://ecommerce_app;
        proxy_set_header Host $host;
    }

    # Frontend pages
    location / {
        proxy_pass http://ecommerce_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Apply Configuration

```bash
sudo nginx -t           # Test configuration
sudo systemctl reload nginx
```

---

## SSL/TLS Setup

### Using Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is set up automatically. Verify:
sudo certbot renew --dry-run
```

### Using Self-Signed Certificate (Testing Only)

```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/server.key \
    -out /etc/nginx/ssl/server.crt
```

### SSL Best Practices

- Use TLS 1.2+ only
- Enable HSTS
- Use strong cipher suites
- Set OCSP stapling
- Redirect all HTTP to HTTPS

---

## Database Migration

### Initial Setup

```bash
# Generate initial migration
alembic revision --autogenerate -m "initial schema"

# Apply
alembic upgrade head
```

### Production Migrations

```bash
# Always backup before migrating
pg_dump -U ecom_user -d ecom_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Apply new migrations
alembic upgrade head

# If migration fails, rollback
alembic downgrade -1
```

### Migration Best Practices

1. Always test migrations in staging first
2. Back up production database before applying
3. Schedule migrations during low-traffic periods
4. Review generated migration scripts before applying
5. Keep migrations small and focused

---

## Environment Variables

### Required (Must Change for Production)

```bash
# Generate secure random keys
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Database (use strong password)
DATABASE_URL=postgresql+asyncpg://ecom_user:STRONG_PASSWORD@localhost:5432/ecom_db

# CORS (restrict to your domain)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Optional Tuning

```bash
# Token expiry (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Debug mode (MUST be False in production)
DEBUG=False
```

---

## Monitoring

### Health Check

The application exposes a health endpoint:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### Application Logs

```bash
# Docker
docker-compose logs -f app

# Systemd
journalctl -u ecommerce -f
```

### Database Monitoring

```bash
# Check connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='ecom_db';"

# Check database size
sudo -u postgres psql -c "SELECT pg_size_pretty(pg_database_size('ecom_db'));"
```

### Uptime Monitoring

Set up external monitoring (UptimeRobot, Pingdom, etc.) to check:
- `GET /health` every 60 seconds
- Alert if response is not 200 or response time > 5 seconds

### Log Rotation

For systemd deployments, configure logrotate:

```
/var/log/ecommerce/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## Backup Strategy

### Database Backups

**Automated daily backup:**

```bash
# Create backup script
cat > /opt/scripts/backup_ecommerce.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/ecommerce"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

pg_dump -U ecom_user -d ecom_db | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

# Optional: upload to S3
# aws s3 cp "$BACKUP_DIR/db_$DATE.sql.gz" s3://your-backup-bucket/
EOF

chmod +x /opt/scripts/backup_ecommerce.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /opt/scripts/backup_ecommerce.sh" | crontab -
```

**Docker backup:**

```bash
# Backup database
docker-compose exec postgres pg_dump -U ecom_user ecom_db > backup_$(date +%Y%m%d).sql

# Backup uploaded files
docker cp ecommerce_app:/app/app/static/images/uploads ./uploads_backup_$(date +%Y%m%d)
```

### Restore

```bash
# Restore database
pg_restore -U ecom_user -d ecom_db < backup_20260115.sql
# Or for plain SQL:
psql -U ecom_user -d ecom_db < backup_20260115.sql

# Docker restore
docker-compose exec -T postgres psql -U ecom_user -d ecom_db < backup.sql
```

### Static Files

```bash
# Backup uploads
tar -czf static_backup_$(date +%Y%m%d).tar.gz app/static/images/uploads/
```

---

## Troubleshooting

### Common Issues

**Application won't start:**
```bash
# Check logs
docker-compose logs app
# or
journalctl -u ecommerce -n 50

# Verify database connection
docker-compose exec app python -c "import asyncio; from app.db import engine; asyncio.run(engine.connect())"
```

**Database connection refused:**
```bash
# Verify PostgreSQL is running
sudo systemctl status postgresql
# or
docker-compose ps postgres

# Check connection string
psql -U ecom_user -d ecom_db -c "SELECT 1;"
```

**502 Bad Gateway:**
```bash
# Application may be starting up - wait 30 seconds
# Check if uvicorn is running
ps aux | grep uvicorn

# Check port
netstat -tlnp | grep 8000
```

**Permission errors on static files:**
```bash
sudo chown -R www-data:www-data /var/www/ecommerce/app/static/
sudo chmod -R 755 /var/www/ecommerce/app/static/
```

**Slow response times:**
```bash
# Check database connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check memory
free -h

# Check uvicorn workers
ps aux | grep uvicorn
```

### Performance Tuning

1. **Database connection pool**: Adjust `pool_size` and `max_overflow` in `app/db.py`
2. **Uvicorn workers**: Use `--workers 4` (or 2x CPU cores)
3. **Nginx worker connections**: Set `worker_connections` to 1024+
4. **PostgreSQL shared_buffers**: Set to 25% of system RAM
5. **Enable Redis caching**: Add caching layer for frequently accessed data

---

## Scaling

### Horizontal Scaling

1. Add more uvicorn workers
2. Use load balancer (Nginx upstream with multiple app servers)
3. Session data in Redis instead of in-memory
4. Shared static file storage (S3, NFS)

### Vertical Scaling

1. Increase server RAM/CPU
2. Increase PostgreSQL `shared_buffers` and `work_mem`
3. Optimize slow queries with EXPLAIN ANALYZE
4. Add database read replicas
