# Docker Development Environment

This document explains how to use the Docker-based development environment for the AI Finance Platform. Everything runs in containers - no local Python installation needed!

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- Git
- Make (optional, but recommended)

## Quick Start

### 1. Build the Development Environment

```bash
make dev-build
```

This builds a complete Python 3.11 development container with all dependencies.

### 2. Start the Development Environment

```bash
make dev-up
```

This starts:
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- Development container (with all code and dependencies)

### 3. Enter the Development Container

```bash
make dev-shell
```

You're now inside the container! All dependencies are installed and ready.

### 4. Run Tests

Inside the container:
```bash
poetry run pytest -v
```

Or from your host machine:
```bash
make dev-test
```

## Development Workflow

### Working with Code

All your code is mounted into the container at `/app`. Any changes you make on your host machine are immediately reflected in the container.

### Running Commands

You have two options:

**Option 1: Inside the container (recommended for interactive work)**
```bash
make dev-shell
# Now you're inside the container
poetry run pytest
poetry run python -m app.ml.train_model
poetry run alembic upgrade head
```

**Option 2: From host machine (quick commands)**
```bash
make dev-test          # Run tests
make dev-migrate       # Run migrations
make dev-train         # Train ML models
```

### Database Operations

**Access PostgreSQL shell:**
```bash
make db-shell
```

**Reset database (WARNING: deletes all data):**
```bash
make db-reset
```

**Run migrations:**
```bash
make dev-migrate
```

### Viewing Logs

```bash
make dev-logs
```

Press Ctrl+C to stop viewing logs.

## Container Architecture

### Services

1. **postgres** - PostgreSQL 16 database
   - Port: 5432
   - User: postgres
   - Password: postgres
   - Databases: ai_finance_platform, ai_finance_platform_test

2. **redis** - Redis 7 cache
   - Port: 6379

3. **dev** - Development container
   - Python 3.11
   - All project dependencies installed via Poetry
   - Code mounted from host
   - Persistent volumes for Poetry cache and ML models

4. **app** - Production-like FastAPI server (optional)
   - Port: 8001
   - Auto-reload enabled

### Volumes

- `postgres_data` - Database persistence
- `redis_data` - Redis persistence
- `poetry_cache` - Poetry package cache (speeds up rebuilds)
- `pip_cache` - Pip package cache
- `./models` - ML model storage (shared with host)

## Common Tasks

### Install New Python Package

```bash
make dev-shell
poetry add <package-name>
# Or for dev dependencies:
poetry add --group dev <package-name>
```

The `pyproject.toml` and `poetry.lock` files on your host will be updated automatically.

### Create Database Migration

```bash
make dev-shell
poetry run alembic revision --autogenerate -m "description of changes"
poetry run alembic upgrade head
```

### Train ML Models

```bash
make dev-train
```

Models are saved to `./models` directory (shared with host).

### Run Specific Tests

```bash
make dev-shell
poetry run pytest tests/test_models.py -v
poetry run pytest tests/test_transaction_service.py::test_create_transaction -v
```

### Run Tests with Coverage

```bash
make dev-test-cov
```

Coverage report will be in `htmlcov/index.html`.

## Troubleshooting

### Container won't start

```bash
# Check container logs
docker-compose logs dev

# Rebuild from scratch
make dev-clean
make dev-build
make dev-up
```

### Database connection issues

```bash
# Check if PostgreSQL is healthy
docker ps

# Restart database
docker-compose restart postgres

# Check database logs
docker-compose logs postgres
```

### Permission issues with volumes

On Linux, you might need to adjust permissions:
```bash
sudo chown -R $USER:$USER models/
```

### Clean slate

```bash
# Remove everything and start fresh
make dev-clean
make dev-build
make dev-up
```

## Environment Variables

Environment variables are set in `docker-compose.yml` for the dev container:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `DEBUG` - Debug mode (true/false)
- `LOG_LEVEL` - Logging level
- `SECRET_KEY` - JWT secret key
- `ENCRYPTION_KEY` - Data encryption key

For production, use `.env` file or environment-specific configuration.

## Performance Tips

1. **Use volumes for caching** - Poetry and pip caches are persisted in volumes
2. **Keep container running** - Use `make dev-shell` instead of restarting
3. **Selective testing** - Run specific tests instead of full suite during development
4. **Use .dockerignore** - Exclude unnecessary files from build context

## Differences from Local Development

### Advantages of Docker Development

✅ Consistent environment across all developers
✅ No Python version conflicts
✅ No system dependency issues
✅ Easy to reset to clean state
✅ Matches production environment
✅ Isolated from host system

### When to Use Local Development

- IDE debugging with breakpoints (though many IDEs support Docker debugging)
- Very quick iteration on small changes
- Limited Docker resources

## Next Steps

1. Start the environment: `make dev-up`
2. Enter the container: `make dev-shell`
3. Run tests: `poetry run pytest -v`
4. Start coding!

For more commands, run:
```bash
make help
```
