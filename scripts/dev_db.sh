#!/usr/bin/env bash
set -e

# Absolute path to the project directory
PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)

COMPOSE_FILE="${PROJECT_DIR}/../docker/docker-compose.yml"

# Start services in detached mode
docker compose -f "$COMPOSE_FILE" up -d

echo "🚀 Dev services up:"
# echo "  • Postgres at localhost:5432 (user: scoreadmin / pass: scorepass / db: scoresight)"
echo "  • Redis    at localhost:6379"