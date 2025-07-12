.PHONY: dev db run celery lint test cov db-init db-migrate db-upgrade db-downgrade install setup-dev setup-prod docker-build docker-up docker-down docker-logs help

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo "ScoreSight Development Commands"
	@echo "==============================="
	@echo
	@echo "Environment Setup:"
	@echo "  setup-dev     Setup development environment with dev dependencies"
	@echo "  setup-prod    Setup production environment with production dependencies"
	@echo
	@echo "Docker Commands:"
	@echo "  docker-build  Build Docker images"
	@echo "  docker-up     Start all services with Docker (production)"
	@echo "  docker-dev    Start development environment with Docker"
	@echo "  docker-down   Stop all Docker services"
	@echo "  docker-restart Restart Docker services"
	@echo "  docker-logs   View Docker logs"
	@echo "  docker-clean  Clean Docker resources"
	@echo
	@echo "Environment Files:"
	@echo "  .env          Main environment variables (local development)"
	@echo "  .env.docker   Docker production overrides"
	@echo "  .env.dev      Docker development overrides"
	@echo "  .env.production Production template"
	@echo
	@echo "Local Development:"
	@echo "  dev-full      Start Redis + Celery + Flower + FastAPI"
	@echo "  dev-monitor   Start Celery + Flower in foreground"
	@echo "  run           Start only FastAPI server"
	@echo "  celery        Start only Celery worker"
	@echo "  celery-monitor Start Celery with Flower monitoring"
	@echo
	@echo "Database:"
	@echo "  db-init       Initialize database"
	@echo "  db-migrate    Create new migration"
	@echo "  db-upgrade    Apply migrations"
	@echo "  db-downgrade  Rollback migration"
	@echo
	@echo "Testing & Quality:"
	@echo "  test          Run all tests"
	@echo "  test-api      Run API tests only"
	@echo "  lint          Lint and format code"
	@echo "  cov           Generate coverage report"
	@echo

# =============================================================================
# Environment Setup
# =============================================================================

# Setup development environment
setup-dev:
	@echo "Setting up development environment..."
	@./scripts/setup_env.sh dev

# Setup production environment
setup-prod:
	@echo "Setting up production environment..."
	@./scripts/setup_env.sh prod

# Install dependencies (legacy - use setup-dev or setup-prod instead)
install:
	@echo "Installing dependencies..."
	@pip install -r requirements.txt

# =============================================================================
# Docker Commands
# =============================================================================

# Build Docker images
docker-build:
	@echo "Building Docker images..."
	@docker compose build

# Start all services with Docker
docker-up:
	@echo "Starting all services with Docker..."
	@docker compose up -d
	@echo "Services started:"
	@echo "  • API:    http://localhost:8001"
	@echo "  • Flower: http://localhost:5555 (admin:admin123)"
	@echo "  • Redis:  localhost:6379"

# Start development with Docker
docker-dev:
	@echo "Starting development with Docker..."
	@docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Stop all Docker services
docker-down:
	@echo "Stopping all Docker services..."
	@docker compose down

# View Docker logs
docker-logs:
	@echo "Viewing Docker logs..."
	@docker compose logs -f

# Restart Docker services
docker-restart: docker-down docker-up

# Clean Docker resources
docker-clean:
	@echo "Cleaning Docker resources..."
	@docker compose down -v --rmi all
	@docker system prune -f

# =============================================================================
# Local Development
# =============================================================================

# Development environment setup
dev: 
	@echo "Starting development environment..."
	@echo "Use 'make run' in one terminal and 'make celery' in another"
	@echo "Or use 'make dev-full' to start everything with monitoring"
	@echo "Or use 'make docker-dev' for Docker development"

# Start full development environment (Redis + FastAPI + Celery + Flower)
dev-full: db-init
	@echo "Starting full development environment..."
	@echo "1. Starting Redis..."
	@./scripts/dev_db.sh &
	@sleep 2
	@echo "2. Starting Celery worker in background..."
	@celery -A app.celery_app worker --loglevel=info --concurrency=2 --detach
	
	@echo "3. Starting FastAPI server..."
	@echo "   API will be available at http://localhost:8001"
	@python app.py
	@echo "4. Starting Flower monitoring..."
	@echo "   Flower will be available at http://localhost:5555"
	@celery -A app.celery_app flower --port=5555 --detach

# Start development with Docker
docker-dev:
	@echo "Starting development with Docker..."
	@docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Start development with monitoring (Celery + Flower in foreground for debugging)
dev-monitor: db-init
	@echo "Starting development with monitoring..."
	@echo "This will start Celery worker and Flower monitoring"
	@echo "Use 'make run' in another terminal to start the API"
	@echo "Flower will be available at http://localhost:5555"
	@echo "Press Ctrl+C to stop both worker and monitoring"
	@make celery-full

# =============================================================================
# Database Commands
# =============================================================================

# Initialize database
db-init:
	@echo "Initializing database..."
	@alembic upgrade head

# Create new migration
db-migrate:
	@echo "Creating new migration..."
	@alembic revision --autogenerate -m "$(msg)"

# Apply migrations
db-upgrade:
	@echo "Applying database migrations..."
	@alembic upgrade head

# Rollback migrations
db-downgrade:
	@echo "Rolling back database migration..."
	@alembic downgrade -1

# Spin up Redis via Docker Compose
db:
	@echo "Launching Redis via Docker Compose..."
	@./scripts/dev_db.sh

# Run FastAPI server with auto-reload
run:
	@echo "Starting Redis and FastAPI server..."
	@./scripts/dev_db.sh
	@echo "Running FastAPI server..."
	@python app.py

# Start Celery worker for background tasks
celery:
	@echo "Starting Celery worker..."
	@celery -A app.celery_app worker --loglevel=info --concurrency=2

# Start Celery worker with enhanced logging and debugging
celery-debug:
	@echo "Starting Celery worker with debug logging..."
	@celery -A app.celery_app worker --loglevel=debug --concurrency=1 --pool=solo

# Start Celery with Flower monitoring (web interface)
celery-monitor:
	@echo "Starting Celery with Flower monitoring..."
	@echo "Flower will be available at http://localhost:5555"
	@celery -A app.celery_app flower --port=5555

# Start both Celery worker and Flower in background
celery-full:
	@echo "Starting Celery worker and Flower monitoring..."
	@echo "Worker starting in background..."
	@celery -A app.celery_app worker --loglevel=info --concurrency=2 --detach
	@echo "Flower starting on http://localhost:5555"
	@celery -A app.celery_app flower --port=5555

# Stop all Celery processes
celery-stop:
	@echo "Stopping all Celery processes..."
	@pkill -f "celery.*scoresight" || echo "No Celery processes found"

# Show Celery status
celery-status:
	@echo "Checking Celery status..."
	@celery -A app.celery_app status

# Purge all tasks from queue
celery-purge:
	@echo "Purging all tasks from queue..."
	@celery -A app.celery_app purge

# Test the API
test-api:
	@echo "Testing API endpoints..."
	@python -m pytest tests/api/ -v

# Run all tests
test:
	@echo "Running all tests..."
	@python -m pytest tests/ -v

lint:
	@echo "Linting code..."
	@black scoresight tests
	@isort scoresight tests
	mypy scoresight tests

cov:
	pytest --cov=scoresight --cov-report=term-missing
	@echo "Code coverage report generated. Check the output above for details."