.PHONY: dev db run celery lint test cov db-init db-migrate db-upgrade db-downgrade install

# Install dependencies
install:
	@echo "Installing dependencies..."
	@pip install -r requirements.txt

# Development environment setup
dev: db-init
	@echo "Starting development environment..."
	@echo "Use 'make run' in one terminal and 'make celery' in another"
	@echo "Or use 'make dev-full' to start everything with monitoring"

# Start full development environment (Redis + FastAPI + Celery + Flower)
dev-full: db-init
	@echo "Starting full development environment..."
	@echo "1. Starting Redis..."
	@./scripts/dev_db.sh &
	@sleep 2
	@echo "2. Starting Celery worker in background..."
	@celery -A app.celery_app worker --loglevel=info --concurrency=2 --detach
	@echo "3. Starting Flower monitoring..."
	@echo "   Flower will be available at http://localhost:5555"
	@celery -A app.celery_app flower --port=5555 --detach
	@echo "4. Starting FastAPI server..."
	@echo "   API will be available at http://localhost:8001"
	@python app.py

# Start development with monitoring (Celery + Flower in foreground for debugging)
dev-monitor: db-init
	@echo "Starting development with monitoring..."
	@echo "This will start Celery worker and Flower monitoring"
	@echo "Use 'make run' in another terminal to start the API"
	@echo "Flower will be available at http://localhost:5555"
	@echo "Press Ctrl+C to stop both worker and monitoring"
	@make celery-full

# Initialize database
db-init:
	@echo "Initializing database..."
	@cd scoresight && alembic upgrade head

# Create new migration
db-migrate:
	@echo "Creating new migration..."
	@cd scoresight && alembic revision --autogenerate -m "$(msg)"

# Apply migrations
db-upgrade:
	@echo "Applying database migrations..."
	@cd scoresight && alembic upgrade head

# Rollback migrations
db-downgrade:
	@echo "Rolling back database migration..."
	@cd scoresight && alembic downgrade -1

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