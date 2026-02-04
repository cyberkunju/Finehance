.PHONY: help install dev test lint format clean docker-up docker-down migrate dev-build dev-up dev-down dev-shell dev-logs dev-test dev-migrate

help:
	@echo "=== AI Finance Platform - Development Commands ==="
	@echo ""
	@echo "Docker Development (Recommended):"
	@echo "  make dev-build       - Build development Docker containers"
	@echo "  make dev-up          - Start all development containers"
	@echo "  make dev-down        - Stop all development containers"
	@echo "  make dev-shell       - Open bash shell in dev container"
	@echo "  make dev-logs        - View logs from all containers"
	@echo "  make dev-test        - Run all tests in dev container"
	@echo "  make dev-test-cov    - Run tests with coverage report"
	@echo "  make dev-migrate     - Run database migrations in container"
	@echo "  make dev-train       - Train ML models in container"
	@echo "  make dev-restart     - Restart development containers"
	@echo "  make dev-clean       - Remove containers and volumes"
	@echo ""
	@echo "Database:"
	@echo "  make db-shell        - Open PostgreSQL shell"
	@echo "  make db-reset        - Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Local Development (Legacy):"
	@echo "  make install         - Install dependencies locally"
	@echo "  make test            - Run tests locally"
	@echo "  make lint            - Run linters"
	@echo "  make format          - Format code"

# Docker Development Commands (Primary workflow)
dev-build:
	@echo "Building development containers..."
	docker-compose build dev

dev-up:
	@echo "Starting development environment..."
	docker-compose up -d postgres redis dev
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@echo ""
	@echo "Development environment is ready!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run 'make dev-shell' to enter the development container"
	@echo "  2. Inside container, run 'poetry run pytest' to run tests"
	@echo "  3. Or run 'make dev-test' from host to run tests"

dev-down:
	@echo "Stopping development environment..."
	docker-compose down

dev-shell:
	@echo "Opening shell in development container..."
	@docker exec -it ai-finance-dev /bin/bash

dev-logs:
	docker-compose logs -f

dev-test:
	@echo "Running tests in development container..."
	docker exec -it ai-finance-dev poetry run pytest -v

dev-test-cov:
	@echo "Running tests with coverage in development container..."
	docker exec -it ai-finance-dev poetry run pytest --cov=app --cov-report=html --cov-report=term -v

dev-migrate:
	@echo "Running database migrations in development container..."
	docker exec -it ai-finance-dev poetry run alembic upgrade head

dev-train:
	@echo "Training ML models in development container..."
	docker exec -it ai-finance-dev poetry run python -m app.ml.train_model

dev-restart:
	@echo "Restarting development environment..."
	docker-compose restart dev

dev-clean:
	@echo "Cleaning up development environment..."
	docker-compose down -v
	docker system prune -f

# Database Commands
db-shell:
	@echo "Opening PostgreSQL shell..."
	docker exec -it ai-finance-postgres psql -U postgres -d ai_finance_platform

db-reset:
	@echo "Resetting database..."
	docker exec -it ai-finance-postgres psql -U postgres -c "DROP DATABASE IF EXISTS ai_finance_platform;"
	docker exec -it ai-finance-postgres psql -U postgres -c "DROP DATABASE IF EXISTS ai_finance_platform_test;"
	docker exec -it ai-finance-postgres psql -U postgres -c "CREATE DATABASE ai_finance_platform;"
	docker exec -it ai-finance-postgres psql -U postgres -c "CREATE DATABASE ai_finance_platform_test;"
	$(MAKE) dev-migrate

# Legacy local commands
install:
	poetry install

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=app --cov-report=html --cov-report=term

lint:
	poetry run ruff check app tests
	poetry run mypy app

format:
	poetry run black app tests
	poetry run ruff check --fix app tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

migrate:
	poetry run alembic upgrade head
