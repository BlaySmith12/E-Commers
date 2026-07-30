#!/bin/bash
# ─── Deploy Script ───────────────────────────────────────────────────────────
# Run this on the VPS after pushing changes to the repo:
#   bash deploy.sh
# ──────────────────────────────────────────────────────────────────────────────
set -e

echo "==> Deploying ASAH'S PRIMENEST..."

cd "$(dirname "$0")"

# ─── Pull latest code ────────────────────────────────────────────────────────
echo "Pulling latest changes..."
git pull origin main || git pull origin master

# ─── Ensure .env exists ─────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Copy .env.production to .env and configure it first."
    exit 1
fi

# ─── Stop existing containers ────────────────────────────────────────────────
echo "Stopping existing containers..."
docker compose down

# ─── Build and start ────────────────────────────────────────────────────────
echo "Building and starting containers..."
docker compose up -d --build

# ─── Wait for health ────────────────────────────────────────────────────────
echo "Waiting for application to be healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "Application is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "WARNING: Application health check timed out. Check logs:"
        echo "  docker compose logs app"
    fi
    sleep 2
done

# ─── Initial SSL (first deploy only) ────────────────────────────────────────
if ! docker compose exec nginx test -f /etc/letsencrypt/live/asahsprimenest.com/fullchain.pem 2>/dev/null; then
    echo ""
    echo "==> No SSL certificate found. To obtain one, run:"
    echo "  docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d YOUR_DOMAIN"
    echo ""
fi

echo ""
echo "==> Deployment complete!"
echo ""
docker compose ps
