#!/bin/bash

# Setup script for AI Finance Platform

set -e

echo "🚀 Setting up AI Finance Platform..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration (especially SECRET_KEY and ENCRYPTION_KEY)"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
poetry install

# Start Docker services
echo "🐳 Starting Docker services (PostgreSQL and Redis)..."
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Run database migrations
echo "🗄️  Running database migrations..."
poetry run alembic upgrade head

echo "✅ Setup complete!"
echo ""
echo "To start the development server, run:"
echo "  poetry run uvicorn app.main:app --reload"
echo ""
echo "Or use Docker Compose:"
echo "  docker-compose up"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
