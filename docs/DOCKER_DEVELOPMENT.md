# Docker Development Environment

Everything runs in containers — no local Python installation needed.

---

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- Git
- Make (optional, but recommended)
- NVIDIA GPU + nvidia-docker (optional, for AI Brain only)

---

## Services Overview

The `docker-compose.yml` defines 7 services across 3 profiles:

| Service | Image / Build | Port | Profile | Description |
|---------|--------------|------|---------|-------------|
| **postgres** | `postgres:16-alpine` | 5432 | default | PostgreSQL database |
| **redis** | `redis:7-alpine` | 6379 | default | Cache, sessions, token blacklist |
| **dev** | `Dockerfile.dev` | 8000 | default | Development backend (hot reload) |
| **app** | `Dockerfile` | 8001 | default | Production backend (non-root) |
| **ai-brain** | `Dockerfile.ai-brain` | 8080 | `gpu` | LLM inference (NVIDIA GPU required) |
| **prometheus** | `prom/prometheus:v2.49.1` | 9090 | `monitoring` | Metrics scraping + alerting |
| **grafana** | `grafana/grafana:10.3.1` | 3001 | `monitoring` | Dashboards |

---

## Quick Start

### 1. Start Core Services

```bash
# Using Make
make dev-build
make dev-up

# Or directly with docker-compose
docker-compose up -d --build
```

This starts: PostgreSQL (5432), Redis (6379), dev backend (8000), prod backend (8001).

### 2. Run Migrations

```bash
# The dev container runs migrations automatically on startup, but to run manually:
docker-compose exec dev alembic upgrade head
```

### 3. Enter the Dev Container

```bash
make dev-shell
# Or:
docker-compose exec dev bash
```

You're now inside the container with all Python dependencies installed via Poetry.

### 4. Run Tests

```bash
# Inside the container
poetry run pytest tests/ -v

# From host
make dev-test
```

### 5. Access the Application

| Service | URL |
|---------|-----|
| Backend API (dev) | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Backend API (prod) | http://localhost:8001 |
| Health check | http://localhost:8000/health |

---

## Development Workflow

### Code Mounting

All source code is mounted into the dev container at `/app`. Changes on the host machine are immediately reflected inside the container. Uvicorn runs with `--reload` for automatic restart on code changes.

### Running Commands

**Option 1: Inside the container (recommended for interactive work)**
```bash
make dev-shell
poetry run pytest
poetry run python -m app.ml.train_model
poetry run alembic upgrade head
```

**Option 2: From host machine (quick commands)**
```bash
make dev-test          # Run tests
make dev-migrate       # Run migrations
```

### Database Operations

```bash
# Access PostgreSQL shell
docker-compose exec postgres psql -U postgres -d ai_finance_platform

# Create a new migration
docker-compose exec dev alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec dev alembic upgrade head

# Rollback one migration
docker-compose exec dev alembic downgrade -1
```

### Redis Operations

```bash
# Access Redis CLI
docker-compose exec redis redis-cli

# Check keys
docker-compose exec redis redis-cli KEYS "*"

# Flush cache
docker-compose exec redis redis-cli FLUSHALL
```

---

## Optional: AI Brain (GPU)

Requires an NVIDIA GPU with Docker GPU support configured.

### Start AI Brain

```bash
docker-compose --profile gpu up -d ai-brain
```

### Verify

```bash
curl http://localhost:8080/health
```

### Configuration

The backend connects to the AI Brain via `AI_BRAIN_URL` environment variable (default: `http://ai-brain:8080`). Set in `.env`:

```ini
AI_BRAIN_URL=http://ai-brain:8080
AI_BRAIN_MODE=http
AI_BRAIN_TIMEOUT=30
```

When AI Brain is unavailable, the backend falls back gracefully (circuit breaker pattern).

---

## Optional: Monitoring Stack

### Start Monitoring

```bash
docker-compose --profile monitoring up -d
```

### Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3001 | admin / admin |

### What's Monitored

- **Prometheus** scrapes:
  - Backend API at `dev:8000` (10s interval)
  - AI Brain at `ai-brain:8080` (30s interval)
  - Self-monitoring at `localhost:9090`
- **18 alert rules** in `prometheus/alerts.yml`
- **Grafana dashboard** for AI Brain metrics in `grafana/dashboards/ai_brain.json`
- **Metrics collected**: 18 AI-specific + 13 GPU metrics + standard HTTP metrics

---

## Frontend Development

The frontend runs outside Docker on the host machine:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
# Available at http://localhost:5173
```

The frontend `.env` should point to the dev backend:
```ini
VITE_API_BASE_URL=http://localhost:8000
```

---

## Volumes

Docker Compose manages persistent data through named volumes:

| Volume | Purpose |
|--------|---------|
| `postgres_data` | PostgreSQL data directory |
| `redis_data` | Redis persistence |
| `poetry_cache` | Poetry package cache |
| `pip_cache` | Pip download cache |
| `hf_cache` | HuggingFace model cache |
| `prometheus_data` | Prometheus TSDB |
| `grafana_data` | Grafana config and dashboards |

### Reset Data

```bash
# Stop all services and remove volumes
docker-compose down -v

# Rebuild from scratch
docker-compose up -d --build
```

---

## Troubleshooting

### Port Conflicts

If a port is already in use, modify the port mapping in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # Changed from 5432 to 5433
```

### Database Connection Issues

```bash
# Check if postgres is healthy
docker-compose ps postgres

# View postgres logs
docker-compose logs postgres

# Manually check connectivity
docker-compose exec dev python -c "from app.database import engine; print(engine.url)"
```

### Container Won't Start

```bash
# View logs for the failing service
docker-compose logs dev

# Rebuild the image
docker-compose build --no-cache dev
```

### Redis Connection Issues

```bash
# Check Redis health
docker-compose exec redis redis-cli ping
# Expected: PONG
```

---

## Make Commands Reference

| Command | Description |
|---------|-------------|
| `make dev-build` | Build development containers |
| `make dev-up` | Start development environment |
| `make dev-down` | Stop all containers |
| `make dev-shell` | Enter dev container shell |
| `make dev-test` | Run pytest inside dev container |
| `make dev-migrate` | Run Alembic migrations |
