#!/bin/sh

# Install openssl for self-signed cert generation (only on first run)
if ! command -v openssl > /dev/null 2>&1; then
    apk add --no-cache openssl > /dev/null 2>&1
fi

# Check if Let's Encrypt cert exists
if [ -f /etc/letsencrypt/live/primenest.com/fullchain.pem ]; then
    echo "SSL certificate found, using HTTPS config"
    cp /etc/nginx/conf.d/https.conf /etc/nginx/nginx.conf
else
    echo "No SSL certificate yet, generating temporary self-signed cert"
    mkdir -p /etc/letsencrypt/live/primenest.com
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/letsencrypt/live/primenest.com/privkey.pem \
        -out /etc/letsencrypt/live/primenest.com/fullchain.pem \
        -subj "/CN=primenest.com/O=Development/C=US" 2>&1
    if [ -f /etc/letsencrypt/live/primenest.com/fullchain.pem ]; then
        echo "Self-signed cert generated successfully"
        cp /etc/nginx/conf.d/https.conf /etc/nginx/nginx.conf
    else
        echo "ERROR: Failed to generate self-signed cert, falling back to HTTP only"
        cat > /etc/nginx/nginx.conf << 'HTTPEOF'
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile        on;
    keepalive_timeout 65;
    client_max_body_size 16M;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 256;
    gzip_types text/plain text/css text/javascript application/javascript application/json application/xml image/svg+xml;

    upstream app {
        server app:8000;
    }

    server {
        listen 80;
        server_name _;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location /static/ {
            alias /app/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
            access_log off;
        }

        location /api/ {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
HTTPEOF
    fi
fi

exec nginx -g "daemon off;"
