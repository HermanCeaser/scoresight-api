#!/usr/bin/env bash
set -e

# Absolute path to the project directory
PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)

COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"

# Start only Redis service in detached mode
docker compose -f "$COMPOSE_FILE" up redis -d

echo "🚀 Dev services up:"
echo "  • Redis    at localhost:6379"