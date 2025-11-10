#!/bin/bash
set -e

# Parse arguments
MODE="prod"
if [ "$1" == "--dev" ]; then
    MODE="dev"
    COMPOSE_FILE="docker-compose.dev.yml"
    PORT_PATTERN="300[0-9]"
elif [ "$1" == "--prod" ] || [ -z "$1" ]; then
    MODE="prod"
    COMPOSE_FILE="docker-compose.yml"
    PORT_PATTERN="8655"
    IMAGE_TAG="ghcr.io/deduparr-dev/deduparr:latest"
else
    echo "❌ Invalid argument. Use --dev or --prod (default)"
    exit 1
fi

# Change to project directory
cd /workspaces/deduparr

echo "🔄 Starting Docker rebuild process (${MODE} mode)..."
echo ""

# 1. Stop and remove containers using the relevant ports
echo "🔍 Checking for containers using ports (${PORT_PATTERN})..."
if [ "$MODE" == "dev" ]; then
    # For dev mode, check ports 3000 and 3001
    CONTAINERS=$(docker ps -a --format "{{.ID}} {{.Ports}}" | grep -E "300[0-9]" | awk '{print $1}' || true)
else
    # For prod mode, check port 8655
    CONTAINERS=$(docker ps -a --format "{{.ID}} {{.Ports}}" | grep "8655" | awk '{print $1}' || true)
fi

if [ -n "$CONTAINERS" ]; then
    echo "🛑 Stopping and removing containers..."
    echo "$CONTAINERS" | xargs -r docker rm -f
    echo "✅ Port containers removed"
else
    echo "✅ No containers using the ports"
fi
echo ""

# 2. Docker compose down
echo "📦 Running docker compose down..."
docker compose -f ${COMPOSE_FILE} down
echo "✅ Compose down complete"
echo ""

# 3. Remove database and encryption key
echo "🗑️  Removing database and encryption key..."
rm -f config/deduparr.db config/deduparr.db-shm config/deduparr.db-wal config/.encryption_key
echo "✅ Database and encryption key removed"
echo ""

# 4. System prune
echo "🧹 Cleaning up Docker system..."
docker system prune -af
echo "✅ Docker system cleaned"
echo ""

# 5. Rebuild without cache
echo "🔨 Building Docker image (no cache)..."
if [ "$MODE" == "dev" ]; then
    docker compose -f ${COMPOSE_FILE} build --no-cache
else
    docker build --no-cache -t ${IMAGE_TAG} .
fi
echo "✅ Build complete"
echo ""

# 6. Start containers
echo "🚀 Starting containers..."
docker compose -f ${COMPOSE_FILE} up -d
echo "✅ Containers started"
echo ""

echo "✨ Docker rebuild complete (${MODE} mode)!"
echo ""
echo "📊 View logs with: docker compose -f ${COMPOSE_FILE} logs -f"
if [ "$MODE" == "dev" ]; then
    echo "🌐 Frontend: http://localhost:3000"
    echo "🔧 Backend:  http://localhost:3001"
else
    echo "🌐 Setup at: http://127.0.0.1:8655/setup"
fi
