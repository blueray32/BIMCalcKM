#!/bin/bash

# Deployment Automation Script for BIMCalc
# Usage: ./deploy.sh <USER>@<HOST>

set -e

TARGET=$1

if [ -z "$TARGET" ]; then
    echo "Usage: ./deploy.sh <USER>@<HOST>"
    echo "Example: ./deploy.sh root@192.168.1.100"
    exit 1
fi

echo "🚀 Starting deployment to $TARGET..."

# 1. Check SSH connection
echo "📡 Checking connection..."
# Disable StrictHostKeyChecking to avoid interactive prompt for new servers
# Use the generated deployment key if it exists
SSH_KEY=""
if [ -f "deployment/deploy_key" ]; then
    SSH_KEY="-i deployment/deploy_key"
fi
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $SSH_KEY"

ssh $SSH_OPTS -o BatchMode=yes -o ConnectTimeout=5 "$TARGET" echo "Connection successful" || {
    echo "❌ Could not connect to $TARGET. Check your SSH keys and IP address."
    exit 1
}

# 2. Prepare remote directory
echo "Tb Preparing remote directory..."
ssh $SSH_OPTS "$TARGET" "mkdir -p /opt/bimcalc/deployment /opt/bimcalc/scripts/postgres"

# 3. Copy files
echo "Tb Copying configuration files..."
scp $SSH_OPTS docker-compose.prod.yml "$TARGET":/opt/bimcalc/docker-compose.yml
scp $SSH_OPTS production.env "$TARGET":/opt/bimcalc/.env
scp $SSH_OPTS deployment/nginx.conf "$TARGET":/opt/bimcalc/deployment/nginx.conf
scp $SSH_OPTS scripts/postgres/init.sql "$TARGET":/opt/bimcalc/scripts/postgres/init.sql
scp $SSH_OPTS Dockerfile "$TARGET":/opt/bimcalc/Dockerfile
scp $SSH_OPTS pyproject.toml "$TARGET":/opt/bimcalc/pyproject.toml
scp $SSH_OPTS README.md "$TARGET":/opt/bimcalc/README.md
scp $SSH_OPTS README_BIMCALC_MVP.md "$TARGET":/opt/bimcalc/README_BIMCALC_MVP.md

# Copy source code (excluding venv/git/etc via rsync if available, or just scp folders)
# Using tar to bundle source for cleaner transfer
echo "📦 Bundling and transferring source code..."
# Explicitly exclude macOS metadata files
tar --exclude='._*' --exclude='.DS_Store' -czf bimcalc_src.tar.gz bimcalc config examples tests scripts alembic.ini
scp $SSH_OPTS bimcalc_src.tar.gz "$TARGET":/opt/bimcalc/
rm bimcalc_src.tar.gz

# 4. Execute remote deployment
echo "🚀 Executing remote deployment..."
ssh $SSH_OPTS "$TARGET" "cd /opt/bimcalc && \
    rm -rf bimcalc && \
    tar -xzf bimcalc_src.tar.gz && \
    rm bimcalc_src.tar.gz && \
    echo 'Installing Docker if missing...' && \
    if ! command -v docker &> /dev/null; then curl -fsSL https://get.docker.com | sh; fi && \
    echo 'Starting services...' && \
    docker compose up -d --build --remove-orphans && \
    echo 'Pruning unused images...' && \
    docker image prune -f && \
    echo '🧹 Cleaning up macOS metadata files inside container...' && \
    docker compose exec -T app find . -name "._*" -delete && \
    echo '🔄 Running database migrations...' && \
    sleep 10 && \
    docker compose exec -T app alembic upgrade head"

echo "✅ Deployment complete! Your app should be running at http://${TARGET#*@}"
echo "📝 To set up SSL, SSH into the server and follow the Nginx/Certbot steps in DIGITALOCEAN_GUIDE.md"
