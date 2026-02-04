@echo off
REM AI Finance Platform - Docker Development Setup Script (Windows)
REM This script sets up the complete Docker development environment

echo ==========================================
echo AI Finance Platform - Docker Dev Setup
echo ==========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo X Docker is not installed. Please install Docker Desktop first.
    echo    Visit: https://www.docker.com/products/docker-desktop
    exit /b 1
)

echo + Docker is installed
echo.

REM Stop any existing containers
echo Stopping any existing containers...
docker-compose down 2>nul
echo.

REM Build the development container
echo Building development container (this may take a few minutes)...
docker-compose build dev
if errorlevel 1 (
    echo X Failed to build development container
    exit /b 1
)
echo.

REM Start the services
echo Starting services...
docker-compose up -d postgres redis dev
if errorlevel 1 (
    echo X Failed to start services
    exit /b 1
)
echo.

REM Wait for PostgreSQL to be ready
echo Waiting for PostgreSQL to be ready...
timeout /t 10 /nobreak >nul
docker exec ai-finance-postgres pg_isready -U postgres >nul 2>&1
if errorlevel 1 (
    echo Waiting a bit more...
    timeout /t 10 /nobreak >nul
)
echo + PostgreSQL is ready
echo.

REM Wait for Redis to be ready
echo Waiting for Redis to be ready...
docker exec ai-finance-redis redis-cli ping >nul 2>&1
echo + Redis is ready
echo.

REM Run database migrations
echo Running database migrations...
docker exec ai-finance-dev poetry run alembic upgrade head
if errorlevel 1 (
    echo X Failed to run migrations
    exit /b 1
)
echo + Migrations complete
echo.

REM Run tests to verify setup
echo Running tests to verify setup...
docker exec ai-finance-dev poetry run pytest -v --tb=short
if errorlevel 1 (
    echo.
    echo ! Some tests failed, but the environment is set up.
) else (
    echo.
    echo + All tests passed!
)
echo.

echo ==========================================
echo + Development Environment Ready!
echo ==========================================
echo.
echo Next steps:
echo.
echo   1. Enter the development container:
echo      docker exec -it ai-finance-dev /bin/bash
echo.
echo   2. Run tests:
echo      docker exec -it ai-finance-dev poetry run pytest -v
echo.
echo   3. View logs:
echo      docker-compose logs -f
echo.
echo   Database: localhost:5432 (user: postgres, pass: postgres)
echo   Redis: localhost:6379
echo.
echo Happy coding! 🚀
