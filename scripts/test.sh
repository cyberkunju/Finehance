#!/bin/bash

# Test script for AI Finance Platform

set -e

echo "🧪 Running tests for AI Finance Platform..."

# Ensure test database is running
echo "🐳 Ensuring test database is available..."
docker-compose up -d postgres redis

# Wait for services
sleep 3

# Run tests with coverage
echo "📊 Running tests with coverage..."
poetry run pytest --cov=app --cov-report=term --cov-report=html -v

echo "✅ Tests complete!"
echo ""
echo "Coverage report available at: htmlcov/index.html"
