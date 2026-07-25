#!/bin/sh

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
        -subj "/CN=primenest.com/O=Development/C=US" 2>/dev/null
    cp /etc/nginx/conf.d/https.conf /etc/nginx/nginx.conf
fi

exec nginx -g "daemon off;"
