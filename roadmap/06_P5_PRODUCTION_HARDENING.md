# Phase 5 — Production Hardening

> **Do this last — after all code is stable and tested**  
> **Estimated Effort:** 3-4 days  
> **Covers:** Rate limiting everywhere, encryption improvements, Docker production config, nginx, monitoring, performance, logging

---

## Task 5.1 — Add Global Rate Limiting

### Problem
Only `app/routes/auth.py` and `app/routes/ai.py` have rate limiting. All other routes are completely unthrottled. An attacker can:
- Flood the prediction endpoint (expensive ARIMA computation)
- Bulk-download all user data via transactions endpoint
- Trigger unlimited ML model training
- Generate unlimited reports (heavy DB queries)

### What To Do

**Create `app/middleware/rate_limiter.py`:**

```python
"""
Global rate limiting middleware using Redis.
Applies per-user (authenticated) or per-IP (unauthenticated) limits.
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.cache import cache_manager

logger = logging.getLogger(__name__)

# Rate limits per endpoint group (requests per minute)
RATE_LIMITS = {
    # Auth endpoints — already have their own limiting, but global fallback
    "/api/auth/": {"per_minute": 20, "per_hour": 100},
    
    # CRUD endpoints — moderate limits
    "/api/transactions": {"per_minute": 60, "per_hour": 500},
    "/api/budgets": {"per_minute": 30, "per_hour": 300},
    "/api/goals": {"per_minute": 30, "per_hour": 300},
    
    # Expensive compute endpoints — strict limits
    "/api/predictions": {"per_minute": 5, "per_hour": 30},
    "/api/reports": {"per_minute": 5, "per_hour": 30},
    "/api/ai/": {"per_minute": 10, "per_hour": 60},
    "/api/ml/train": {"per_minute": 2, "per_hour": 10},
    "/api/ml/categorize/batch": {"per_minute": 5, "per_hour": 30},
    
    # File operations — moderate limits
    "/api/import": {"per_minute": 5, "per_hour": 20},
    "/api/export": {"per_minute": 10, "per_hour": 50},
    
    # Default for any unmatched path
    "_default": {"per_minute": 30, "per_hour": 300},
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip health checks and docs
        if request.url.path in ("/health", "/health/ready", "/health/live", "/docs", "/openapi.json"):
            return await call_next(request)
        
        # Determine rate limit key (user_id from auth or client IP)
        client_id = self._get_client_id(request)
        limits = self._get_limits(request.url.path)
        
        # Check rate limit
        is_allowed, retry_after = await self._check_rate_limit(
            client_id, request.url.path, limits
        )
        
        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )
        
        return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """Get user ID from auth header or fall back to IP."""
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            # Use token hash as key (don't store actual token)
            import hashlib
            return f"user:{hashlib.sha256(auth.encode()).hexdigest()[:16]}"
        
        # Fall back to client IP
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
        return f"ip:{ip}"
    
    def _get_limits(self, path: str) -> dict:
        """Find the most specific rate limit for a path."""
        for prefix, limits in RATE_LIMITS.items():
            if prefix != "_default" and path.startswith(prefix):
                return limits
        return RATE_LIMITS["_default"]
    
    async def _check_rate_limit(self, client_id, path, limits) -> tuple[bool, int]:
        """Sliding window rate limit check using Redis."""
        now = int(time.time())
        minute_key = f"rate:{client_id}:{path}:m:{now // 60}"
        hour_key = f"rate:{client_id}:{path}:h:{now // 3600}"
        
        try:
            minute_count = await cache_manager.get(minute_key)
            minute_count = int(minute_count) if minute_count else 0
            
            if minute_count >= limits["per_minute"]:
                return False, 60 - (now % 60)
            
            hour_count = await cache_manager.get(hour_key)
            hour_count = int(hour_count) if hour_count else 0
            
            if hour_count >= limits["per_hour"]:
                return False, 3600 - (now % 3600)
            
            # Increment counters
            await cache_manager.set(minute_key, str(minute_count + 1), ttl=60)
            await cache_manager.set(hour_key, str(hour_count + 1), ttl=3600)
            
            return True, 0
        except Exception:
            # If Redis is down, allow the request (fail open)
            return True, 0
```

**Register in `app/main.py`:**

```python
from app.middleware.rate_limiter import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware)
```

---

## Task 5.2 — Improve Encryption

### Problem
1. **Hardcoded static salt** `b"ai_finance_platform_salt"` in source code
2. **PBKDF2 iterations** at 100,000 — below OWASP's 2026 recommendation (600,000+)
3. **No key rotation** — if the key is compromised, all data must be re-encrypted manually
4. **Module-level instantiation** crashes the app if `encryption_key` is not configured

### What To Do

**Step 1: Use deployment-specific salt from environment:**

```python
# app/services/encryption_service.py

class EncryptionService:
    def __init__(self, encryption_key: str = None, salt: str = None):
        key = encryption_key or settings.encryption_key
        if not key:
            raise ValueError("ENCRYPTION_KEY must be set in environment")
        
        # Use deployment-specific salt from env, fallback to derived salt
        salt_value = (salt or os.environ.get("ENCRYPTION_SALT", "")).encode()
        if not salt_value:
            # Derive salt from key (not ideal but better than hardcoded)
            import hashlib
            salt_value = hashlib.sha256(key.encode()).digest()[:16]
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_value,
            iterations=600_000,  # Updated to OWASP 2026 recommendation
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        self._fernet = Fernet(derived_key)
```

**Step 2: Lazy initialization to prevent startup crash:**

```python
# Replace module-level singleton
_encryption_service = None

def get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
```

**Step 3: Add to `.env.example`:**

```env
ENCRYPTION_KEY=your-32-character-encryption-key-here
ENCRYPTION_SALT=your-unique-deployment-salt-here
```

---

## Task 5.3 — Add File Upload Size Limits

### Problem
`app/routes/file_import.py` calls `await file.read()` with no size check. A multi-GB file will OOM the server.

### What To Do

**Add size check in the route:**

```python
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("/import/transactions")
async def import_transactions(
    user_id: UUID = Depends(get_current_user_id),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Check content length header
    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB.")
    
    # Read with size limit (for cases where content-length is missing)
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB.")
    
    ...
```

**Also validate file content type (not just extension):**

```python
import magic  # python-magic library

ALLOWED_TYPES = {"text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

mime_type = magic.from_buffer(content[:2048], mime=True)
if mime_type not in ALLOWED_TYPES:
    raise HTTPException(status_code=400, detail=f"Invalid file type: {mime_type}. Only CSV and XLSX are supported.")
```

---

## Task 5.4 — Production Docker Configuration

### What To Do

**Create `docker-compose.prod.yml`:**

```yaml
version: '3.8'

services:
  # === Backend API ===
  api:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    environment:
      - DATABASE_URL=postgresql+asyncpg://finehance:${DB_PASSWORD}@db:5432/finehance
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - ENCRYPTION_SALT=${ENCRYPTION_SALT}
      - SENTRY_DSN=${SENTRY_DSN}
      - DEBUG=false
      - CORS_ORIGINS=https://yourdomain.com
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'

  # === Frontend ===
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "3000:80"
    depends_on:
      - api

  # === PostgreSQL ===
  db:
    image: postgres:16-alpine
    restart: always
    environment:
      - POSTGRES_USER=finehance
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=finehance
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U finehance"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 1G

  # === Redis ===
  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # === Nginx Reverse Proxy ===
  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - api
      - frontend

  # === Prometheus ===
  prometheus:
    image: prom/prometheus:latest
    restart: always
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  # === Grafana ===
  grafana:
    image: grafana/grafana:latest
    restart: always
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - ./grafana:/etc/grafana/provisioning
      - grafana_data:/var/lib/grafana
    ports:
      - "3001:3000"

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

**Create `frontend/Dockerfile`:**

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**Create `nginx/nginx.conf`:**

```nginx
events {
    worker_connections 1024;
}

http {
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';" always;

    # Gzip compression
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;
    gzip_min_length 1000;

    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

    upstream api {
        server api:8000;
    }

    upstream frontend {
        server frontend:80;
    }

    server {
        listen 80;
        server_name yourdomain.com;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;

        # API proxy
        location /api/ {
            limit_req zone=api burst=10 nodelay;
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts for long-running operations (predictions, reports)
            proxy_read_timeout 120s;
            proxy_send_timeout 120s;
        }

        # Auth-specific rate limit
        location /api/auth/ {
            limit_req zone=auth burst=3 nodelay;
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Health checks (no rate limit)
        location /health {
            proxy_pass http://api;
        }

        # Frontend
        location / {
            proxy_pass http://frontend;
        }
    }
}
```

---

## Task 5.5 — Structured Logging

### Problem
Logging is inconsistent. Some services use `logger.info()`, some use `extra=` kwargs, some use f-strings for sensitive data.

### What To Do

**Standardize logging across the app using structured JSON logging:**

Update `app/logging_config.py`:

```python
import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production."""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(debug: bool = False):
    """Configure logging for the application."""
    formatter = JSONFormatter() if not debug else logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

**Call in `app/main.py`:**

```python
from app.logging_config import setup_logging
setup_logging(debug=settings.debug)
```

---

## Task 5.6 — Add Consistent Soft-Delete Across All Entities

### Problem
Transactions use soft-delete (`deleted_at` column). Budgets and Goals use hard-delete (`session.delete()`). This inconsistency means:
- Deleted budgets are gone forever (no undo)
- Foreign key references to deleted budgets/goals break

### What To Do

**Add `deleted_at` to Budget and Goal models:**

```python
# app/models/budget.py
deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

# app/models/goal.py
deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Update services to soft-delete:**

```python
# app/services/budget_service.py
async def delete_budget(self, budget_id, user_id):
    budget = await self.get_budget(budget_id, user_id)
    if not budget:
        return None
    budget.deleted_at = datetime.now(timezone.utc)
    await self.db.flush()
    return budget

# Same for goal_service.py
```

**Add `deleted_at.is_(None)` filter to all read queries for budgets and goals.**

**Create Alembic migration:**

```bash
alembic revision --autogenerate -m "add_soft_delete_to_budgets_and_goals"
alembic upgrade head
```

---

## Task 5.7 — Add Request ID Tracking

### What To Do

Add a middleware that generates a unique request ID for every request, includes it in logs and response headers:

```python
# app/middleware/request_id.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

Register in `main.py`. Use `request.state.request_id` in logging.

---

## Task 5.8 — Create `.env.example` and Deployment Docs

### What To Do

**Create `.env.example`:**

```env
# === Required ===
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/finehance
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change-me-to-a-random-64-char-string
ENCRYPTION_KEY=change-me-to-a-random-32-char-string
ENCRYPTION_SALT=change-me-to-a-random-16-char-string

# === Optional ===
DEBUG=false
SENTRY_DSN=
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# === AI Brain (optional) ===
AI_BRAIN_URL=http://localhost:8080
AI_BRAIN_FALLBACK_THRESHOLD=0.85

# === Monitoring (optional) ===
GRAFANA_PASSWORD=admin
```

---

## Task 5.9 — Performance Optimization Checklist

| Area | Action | Impact |
|------|--------|--------|
| Database | Add missing indexes on frequently queried columns (Transaction.date, Transaction.user_id+category composite) | HIGH |
| Database | Connection pool tuning — adjust `pool_size` and `max_overflow` based on worker count | MEDIUM |
| Redis | Set `maxmemory-policy allkeys-lru` to prevent OOM | MEDIUM |
| API | Add response compression for large list endpoints | LOW |
| ML | Pre-load categorization model at startup (not lazy load) | MEDIUM |
| ARIMA | Cache forecasts for 1 hour in Redis | HIGH |
| Queries | Use `.options(selectinload(...))` for relationship queries to avoid N+1 | MEDIUM |
| Frontend | Add React.lazy() for page-level code splitting | MEDIUM |
| Frontend | Add image optimization and CDN headers | LOW |

---

## Task 5.10 — Add Database Backup Strategy

### What To Do

**Create `scripts/backup.sh`:**

```bash
#!/bin/bash
# Daily PostgreSQL backup script
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="finehance"

# Create backup
pg_dump -U finehance -h db $DB_NAME | gzip > "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Keep only last 30 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: ${DB_NAME}_${TIMESTAMP}.sql.gz"
```

**Add to `docker-compose.prod.yml`:**

```yaml
  backup:
    image: postgres:16-alpine
    volumes:
      - ./scripts/backup.sh:/backup.sh
      - backup_data:/backups
    entrypoint: ["sh", "-c", "while true; do sh /backup.sh; sleep 86400; done"]
    depends_on:
      - db
```

---

## Granular Checklist — Task 5.1 (Global Rate Limiting)

### Implementation
- [ ] Create `app/middleware/rate_limiter.py`
- [ ] Import `cache_manager` from `app.cache`
- [ ] Define `RATE_LIMITS` dict per endpoint group:
  - [ ] `/api/auth/` — 20/min, 100/hour
  - [ ] `/api/transactions` — 60/min, 500/hour
  - [ ] `/api/budgets` — 30/min, 300/hour
  - [ ] `/api/goals` — 30/min, 300/hour
  - [ ] `/api/predictions` — 5/min, 30/hour (expensive compute)
  - [ ] `/api/reports` — 5/min, 30/hour (heavy DB queries)
  - [ ] `/api/ai/` — 10/min, 60/hour
  - [ ] `/api/ml/train` — 2/min, 10/hour (very expensive)
  - [ ] `/api/ml/categorize/batch` — 5/min, 30/hour
  - [ ] `/api/import` — 5/min, 20/hour
  - [ ] `/api/export` — 10/min, 50/hour
  - [ ] `_default` — 30/min, 300/hour
- [ ] Implement `RateLimitMiddleware` class (extends `BaseHTTPMiddleware`)
- [ ] Skip rate limiting for health checks (`/health`, `/health/ready`, `/health/live`)
- [ ] Skip rate limiting for docs (`/docs`, `/openapi.json`)
- [ ] Implement `_get_client_id()` — user token hash (auth) or client IP (unauth)
- [ ] Handle `X-Forwarded-For` header for clients behind proxy
- [ ] Implement `_get_limits()` — find most specific limit for request path
- [ ] Implement `_check_rate_limit()` — sliding window using Redis
- [ ] Use Redis keys: `rate:{client_id}:{path}:m:{minute}` (60s TTL)
- [ ] Use Redis keys: `rate:{client_id}:{path}:h:{hour}` (3600s TTL)
- [ ] Return `429 Too Many Requests` with `Retry-After` header when limit exceeded
- [ ] Fail open if Redis is down (allow request, don't crash)

### Registration
- [ ] Open `app/main.py`
- [ ] Add `from app.middleware.rate_limiter import RateLimitMiddleware`
- [ ] Add `app.add_middleware(RateLimitMiddleware)`

### Verification
- [ ] Test: normal requests → pass through
- [ ] Test: exceed per-minute limit → 429 with `Retry-After`
- [ ] Test: exceed per-hour limit → 429
- [ ] Test: health check endpoints → never rate limited
- [ ] Test: Redis down → requests still pass (fail open)

---

## Granular Checklist — Task 5.2 (Encryption Improvements)

### Environment-based salt
- [ ] Open `app/services/encryption_service.py`
- [ ] Add `ENCRYPTION_SALT` env var read via `os.environ.get()`
- [ ] If no env salt: derive salt from encryption key using SHA-256
- [ ] Remove hardcoded `b"ai_finance_platform_salt"` string

### Iteration count
- [ ] Find PBKDF2 `iterations` parameter
- [ ] Change from `100_000` to `600_000` (OWASP 2026 recommendation)

### Lazy initialization
- [ ] Remove module-level `encryption_service = EncryptionService()` instantiation
- [ ] Create `get_encryption_service()` function with lazy init pattern
- [ ] Use global `_encryption_service` variable
- [ ] Return cached instance on subsequent calls
- [ ] Update all callers to use `get_encryption_service()` instead of direct reference

### Verification
- [ ] App starts without `ENCRYPTION_KEY` → no crash (lazy init)
- [ ] App starts with `ENCRYPTION_KEY` → first encrypt call works
- [ ] Encrypt/decrypt round-trip works with new iteration count
- [ ] Different `ENCRYPTION_SALT` values produce different derived keys

---

## Granular Checklist — Task 5.3 (File Upload Limits)

- [ ] Open `app/routes/file_import.py`
- [ ] Define `MAX_UPLOAD_SIZE = 10 * 1024 * 1024` (10 MB)
- [ ] Add `file.size` check before reading content
- [ ] Add `len(content)` check after reading (for missing Content-Length)
- [ ] Return 413 "File too large" with size limit in message
- [ ] Add file content type validation:
  - [ ] Check if `python-magic` is available (or use file extension fallback)
  - [ ] Define allowed types: `text/csv`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - [ ] Return 400 "Invalid file type" with supported types listed
- [ ] Test: upload 1MB file → success
- [ ] Test: upload 15MB file → 413 error
- [ ] Test: upload .exe file → 400 error
- [ ] Test: upload valid CSV → success

---

## Granular Checklist — Task 5.4 (Production Docker)

### Docker Compose production file
- [ ] Create `docker-compose.prod.yml`
- [ ] Add `api` service:
  - [ ] Build from Dockerfile
  - [ ] Set `restart: always`
  - [ ] Configure all env vars from `.env`
  - [ ] Set `DEBUG=false`
  - [ ] Add health check (curl to `/health/ready`)
  - [ ] Set resource limits (2G memory, 2.0 CPUs)
  - [ ] Depend on `db` and `redis` with health conditions
- [ ] Add `frontend` service:
  - [ ] Build from `frontend/Dockerfile`
  - [ ] Set `restart: always`
  - [ ] Expose port 3000
  - [ ] Depend on `api`
- [ ] Add `db` service (PostgreSQL 16):
  - [ ] Set environment vars (user, password, db name)
  - [ ] Mount persistent volume for data
  - [ ] Mount init SQL script
  - [ ] Add health check (`pg_isready`)
  - [ ] Set resource limit (1G memory)
- [ ] Add `redis` service (Redis 7):
  - [ ] Set `appendonly yes` for persistence
  - [ ] Set `maxmemory 256mb` and `allkeys-lru` policy
  - [ ] Mount persistent volume
  - [ ] Add health check (`redis-cli ping`)
- [ ] Add `nginx` service:
  - [ ] Mount nginx config file
  - [ ] Mount SSL certificate directory
  - [ ] Expose ports 80 and 443
  - [ ] Depend on `api` and `frontend`
- [ ] Add `prometheus` service:
  - [ ] Mount prometheus config
  - [ ] Mount persistent volume
  - [ ] Expose port 9090
- [ ] Add `grafana` service:
  - [ ] Mount provisioning configs
  - [ ] Mount persistent volume
  - [ ] Expose port 3001
  - [ ] Set admin password from env
- [ ] Define all named volumes (postgres_data, redis_data, prometheus_data, grafana_data)

### Frontend Dockerfile
- [ ] Create `frontend/Dockerfile`
- [ ] Stage 1: Build — Node 20-alpine, npm ci, npm run build
- [ ] Stage 2: Serve — nginx:alpine, copy build output to nginx html dir
- [ ] Copy custom nginx config for SPA routing
- [ ] Expose port 80

### Nginx configuration
- [ ] Create `nginx/` directory
- [ ] Create `nginx/nginx.conf`
- [ ] Add security headers:
  - [ ] `X-Frame-Options: SAMEORIGIN`
  - [ ] `X-Content-Type-Options: nosniff`
  - [ ] `X-XSS-Protection: 1; mode=block`
  - [ ] `Referrer-Policy: strict-origin-when-cross-origin`
  - [ ] `Content-Security-Policy` with appropriate directives
- [ ] Enable gzip compression for text/json/js/css
- [ ] Define rate limiting zones:
  - [ ] `api` zone: 30r/m with burst=10
  - [ ] `auth` zone: 5r/m with burst=3
- [ ] Configure upstream for api (port 8000)
- [ ] Configure upstream for frontend (port 80)
- [ ] HTTP server — redirect to HTTPS
- [ ] HTTPS server:
  - [ ] SSL certificate and key paths
  - [ ] TLS 1.2 and 1.3 protocols only
  - [ ] `/api/` location — proxy to api upstream with rate limit
  - [ ] `/api/auth/` location — proxy with stricter rate limit
  - [ ] `/health` location — proxy without rate limit
  - [ ] `/` location — proxy to frontend
  - [ ] Proxy timeout settings (120s for long operations)

### Verification
- [ ] `docker compose -f docker-compose.prod.yml config` → valid YAML
- [ ] `docker compose -f docker-compose.prod.yml build` → builds successfully
- [ ] All services start and pass health checks

---

## Granular Checklist — Task 5.5 (Structured Logging)

- [ ] Open `app/logging_config.py`
- [ ] Create `JSONFormatter` class extending `logging.Formatter`
- [ ] Include fields: timestamp, level, logger, message, module, function, line
- [ ] Include optional fields: user_id, request_id if present
- [ ] Include exception info if present
- [ ] Create `setup_logging(debug)` function
- [ ] Use `JSONFormatter` for production (debug=False)
- [ ] Use human-readable format for development (debug=True)
- [ ] Clear existing root logger handlers
- [ ] Set log level: DEBUG for dev, INFO for prod
- [ ] Silence noisy libraries: httpx, sqlalchemy.engine, uvicorn.access → WARNING
- [ ] Open `app/main.py`
- [ ] Call `setup_logging(debug=settings.debug)` in lifespan
- [ ] Test: production mode → JSON log output
- [ ] Test: debug mode → human-readable log output
- [ ] Test: log lines include module, function, line number

---

## Granular Checklist — Task 5.6 (Consistent Soft-Delete)

### Budget model
- [ ] Open `app/models/budget.py`
- [ ] Add `deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)`
- [ ] Add `from datetime import datetime` import if missing

### Goal model
- [ ] Open `app/models/goal.py`
- [ ] Add `deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)`

### Budget service
- [ ] Open `app/services/budget_service.py`
- [ ] Change `delete_budget` from `session.delete(budget)` to `budget.deleted_at = datetime.now(timezone.utc)`
- [ ] Add `.where(Budget.deleted_at.is_(None))` to `list_budgets` query
- [ ] Add `.where(Budget.deleted_at.is_(None))` to `get_budget` query
- [ ] Add `.where(Budget.deleted_at.is_(None))` to `get_budget_progress` query

### Goal service
- [ ] Open `app/services/goal_service.py`
- [ ] Change `delete_goal` from `session.delete(goal)` to `goal.deleted_at = datetime.now(timezone.utc)`
- [ ] Add `.where(FinancialGoal.deleted_at.is_(None))` to `list_goals` query
- [ ] Add `.where(FinancialGoal.deleted_at.is_(None))` to `get_goal` query
- [ ] Add filter to all other goal read queries

### Migration
- [ ] Create Alembic migration: `alembic revision --autogenerate -m "add_soft_delete_to_budgets_and_goals"`
- [ ] Review migration script for correctness
- [ ] Run migration: `alembic upgrade head`

### Verification
- [ ] Test: delete budget → `deleted_at` set, budget no longer in list
- [ ] Test: delete goal → `deleted_at` set, goal no longer in list
- [ ] Test: deleted budgets/goals still exist in database (queryable by admin)

---

## Granular Checklist — Task 5.7 (Request ID Tracking)

- [ ] Create `app/middleware/request_id.py`
- [ ] Implement `RequestIDMiddleware` class (extends `BaseHTTPMiddleware`)
- [ ] Check for incoming `X-Request-ID` header
- [ ] Generate UUID if no header present
- [ ] Store request ID in `request.state.request_id`
- [ ] Add `X-Request-ID` to response headers
- [ ] Open `app/main.py`
- [ ] Register `RequestIDMiddleware`
- [ ] Test: request without X-Request-ID → response has auto-generated ID
- [ ] Test: request with X-Request-ID → same ID echoed in response
- [ ] Test: request ID shows up in log output

---

## Granular Checklist — Task 5.8 (.env.example)

- [ ] Create `.env.example` file at project root
- [ ] Add `DATABASE_URL` with placeholder value
- [ ] Add `REDIS_URL` with placeholder value
- [ ] Add `JWT_SECRET_KEY` with placeholder and note to change
- [ ] Add `ENCRYPTION_KEY` with placeholder and note to change
- [ ] Add `ENCRYPTION_SALT` with placeholder and note to change
- [ ] Add `DEBUG=false` with comment
- [ ] Add `SENTRY_DSN=` (optional, empty default)
- [ ] Add `CORS_ORIGINS` with localhost defaults
- [ ] Add `AI_BRAIN_URL` (optional)
- [ ] Add `AI_BRAIN_FALLBACK_THRESHOLD` (optional)
- [ ] Add `GRAFANA_PASSWORD` (optional)
- [ ] Add comments explaining required vs optional vars
- [ ] Verify: copy `.env.example` to `.env`, fill values → app starts

---

## Granular Checklist — Task 5.9 (Performance Optimization)

### Database indexes
- [ ] Add index on `Transaction.date` column
- [ ] Add composite index on `Transaction.(user_id, category)` for filtered queries
- [ ] Add composite index on `Transaction.(user_id, date)` for time-range queries
- [ ] Create Alembic migration for new indexes
- [ ] Run migration

### Connection pool tuning
- [ ] Open `app/database.py`
- [ ] Review `pool_size` setting (currently 20)
- [ ] Review `max_overflow` setting (currently 10)
- [ ] Add `pool_pre_ping=True` for stale connection detection
- [ ] Add `pool_recycle=3600` for long-running applications

### Redis configuration
- [ ] Verify `maxmemory-policy allkeys-lru` is set in Redis config
- [ ] Add to docker-compose Redis command if missing

### ML model startup
- [ ] Open `app/ml/categorization_engine.py`
- [ ] Pre-load model at import time (not lazy on first request)
- [ ] Or pre-load in app lifespan startup event

### Frontend code splitting
- [ ] Use `React.lazy()` for DashboardPage
- [ ] Use `React.lazy()` for TransactionsPage
- [ ] Use `React.lazy()` for BudgetsPage
- [ ] Use `React.lazy()` for GoalsPage
- [ ] Use `React.lazy()` for ReportsPage
- [ ] Use `React.lazy()` for SettingsPage
- [ ] Use `React.lazy()` for AIChatPage
- [ ] Use `React.lazy()` for ImportPage
- [ ] Add `<Suspense fallback={<LoadingSkeleton />}>` wrappers

### Verification
- [ ] Database queries use indexes (check with EXPLAIN ANALYZE)
- [ ] First ML categorization request is fast (model pre-loaded)
- [ ] Frontend initial bundle size reduced (check Vite build output)

---

## Granular Checklist — Task 5.10 (Database Backup)

- [ ] Create `scripts/backup.sh`
- [ ] Add `pg_dump` command with gzip compression
- [ ] Add timestamp to backup filename
- [ ] Add cleanup: delete backups older than 30 days
- [ ] Make script executable: `chmod +x scripts/backup.sh`
- [ ] Add `backup` service to `docker-compose.prod.yml`
- [ ] Run backup every 24 hours (86400 seconds sleep loop)
- [ ] Mount `backup_data` volume for persistence
- [ ] Depend on `db` service
- [ ] Test: run backup script → `.sql.gz` file created
- [ ] Test: restore from backup → data intact
- [ ] Document backup/restore procedure in README or deployment docs

---

## Final P5 Validation

- [ ] Rate limiting middleware registered and working
- [ ] Exceed rate limit → 429 response with Retry-After header
- [ ] Encryption uses env-based salt and 600K iterations
- [ ] File uploads > 10MB rejected with 413
- [ ] Invalid file types rejected with 400
- [ ] `docker compose -f docker-compose.prod.yml up` → all services healthy
- [ ] Nginx serves frontend and proxies API correctly
- [ ] Security headers present in all responses
- [ ] Structured JSON logging in production mode
- [ ] Human-readable logging in debug mode
- [ ] Budget/goal soft-delete working (data preserved)
- [ ] Request IDs in all responses and logs
- [ ] `.env.example` documents all required configuration
- [ ] Database has proper indexes
- [ ] ML model pre-loaded at startup
- [ ] Frontend pages lazy-loaded
- [ ] Backup script creates valid backups
- [ ] Load test with 100 concurrent users → acceptable response times
- [ ] OWASP Top 10 checklist reviewed
- [ ] Full deployment on staging server → everything works
