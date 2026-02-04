#!/bin/bash

# AI Finance Platform - Docker Development Setup Script
# This script sets up the complete Docker development environment

set -e

echo "=========================================="
echo "AI Finance Platform - Docker Dev Setup"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop first."
    echo "   Visit: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

echo "✓ Docker is installed"
echo ""

# Check if Make is installed
if ! command -v make &> /dev/null; then
    echo "⚠️  Make is not installed. You can still use docker-compose commands directly."
    echo "   Or install Make for easier commands."
    USE_MAKE=false
else
    echo "✓ Make is installed"
    USE_MAKE=true
fi
echo ""

# Stop any existing containers
echo "Stopping any existing containers..."
docker-compose down 2>/dev/null || true
echo ""

# Build the development container
echo "Building development container (this may take a few minutes)..."
docker-compose build dev
echo ""

# Start the services
echo "Starting services..."
docker-compose up -d postgres redis dev
echo ""

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec ai-finance-postgres pg_isready -U postgres &> /dev/null; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to start"
        exit 1
    fi
    sleep 1
done
echo ""

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
for i in {1..30}; do
    if docker exec ai-finance-redis redis-cli ping &> /dev/null; then
        echo "✓ Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Redis failed to start"
        exit 1
    fi
    sleep 1
done
echo ""

# Run database migrations
echo "Running database migrations..."
docker exec ai-finance-dev poetry run alembic upgrade head
echo "✓ Migrations complete"
echo ""

# Run tests to verify setup
echo "Running tests to verify setup..."
if docker exec ai-finance-dev poetry run pytest -v --tb=short; then
    echo ""
    echo "✓ All tests passed!"
else
    echo ""
    echo "⚠️  Some tests failed, but the environment is set up."
fi
echo ""

echo "=========================================="
echo "✓ Development Environment Ready!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
if [ "$USE_MAKE" = true ]; then
    echo "  1. Enter the development container:"
    echo "     make dev-shell"
    echo ""
    echo "  2. Run tests:"
    echo "     make dev-test"
    echo ""
    echo "  3. View all commands:"
    echo "     make help"
else
    echo "  1. Enter the development container:"
    echo "     docker exec -it ai-finance-dev /bin/bash"
    echo ""
    echo "  2. Run tests:"
    echo "     docker exec -it ai-finance-dev poetry run pytest -v"
    echo ""
    echo "  3. View logs:"
    echo "     docker-compose logs -f"
fi
echo ""
echo "  Database: localhost:5432 (user: postgres, pass: postgres)"
echo "  Redis: localhost:6379"
echo ""
echo "Happy coding! 🚀"
