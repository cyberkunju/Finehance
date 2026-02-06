"""Main FastAPI application entry point."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.cache import cache_manager
from app.config import settings
from app.database import close_db, init_db
from app.logging_config import configure_logging, get_logger, bind_contextvars, clear_contextvars
from app.middleware.security import SecurityMiddleware

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# =============================================================================
# Sentry Integration (Error Tracking)
# =============================================================================
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                LoggingIntegration(
                    level=None,  # Don't capture logs below ERROR
                    event_level=None,  # Don't send logs as events
                ),
            ],
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            environment=settings.environment,
            release=f"{settings.app_name}@{settings.app_version}",
            send_default_pii=False,  # Don't send PII automatically
            attach_stacktrace=True,
            # Performance monitoring
            enable_tracing=True,
        )
        logger.info("Sentry initialized", dsn_configured=True, environment=settings.environment)
    else:
        logger.debug("Sentry not configured - no DSN provided")
except ImportError:
    logger.debug("Sentry SDK not installed - error tracking disabled")

# =============================================================================
# Prometheus Metrics
# =============================================================================
try:
    from prometheus_fastapi_instrumentator import Instrumentator, metrics
    from prometheus_fastapi_instrumentator.metrics import Info

    PROMETHEUS_AVAILABLE = True

    # Create instrumentator with custom metrics
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/health/live", "/health/ready", "/metrics"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    logger.info("Prometheus metrics initialized")
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus-fastapi-instrumentator not installed - metrics disabled")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application", app_name=settings.app_name, version=settings.app_version)

    try:
        # Initialize database
        await init_db()

        # Connect to Redis
        await cache_manager.connect()

        # Initialize GPU metrics collection (if available)
        try:
            from app.metrics.gpu_metrics import gpu_metrics

            if settings.enable_gpu_metrics:
                gpu_metrics.start_collection()
                logger.info("GPU metrics collection started")
        except Exception as e:
            logger.warning("GPU metrics not available", error=str(e))

        logger.info("Application started successfully")

        yield

    finally:
        # Shutdown
        logger.info("Shutting down application")

        # Stop GPU metrics collection
        try:
            from app.metrics.gpu_metrics import gpu_metrics

            gpu_metrics.stop_collection()
        except Exception:
            pass

        # Close database connections
        await close_db()

        # Disconnect from Redis
        await cache_manager.disconnect()

        logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered personal finance management platform",
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# =============================================================================
# Prometheus Metrics Instrumentation
# =============================================================================
if PROMETHEUS_AVAILABLE and settings.enable_metrics:
    # Add default metrics
    instrumentator.add(
        metrics.default(
            metric_namespace="ai_finance",
            metric_subsystem="http",
        )
    )

    # Add request size metric
    instrumentator.add(
        metrics.request_size(
            metric_namespace="ai_finance",
            metric_subsystem="http",
        )
    )

    # Add response size metric
    instrumentator.add(
        metrics.response_size(
            metric_namespace="ai_finance",
            metric_subsystem="http",
        )
    )

    # Add latency histogram
    instrumentator.add(
        metrics.latency(
            metric_namespace="ai_finance",
            metric_subsystem="http",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )
    )

    # Instrument the app and expose /metrics endpoint
    instrumentator.instrument(app).expose(
        app,
        include_in_schema=False,
        should_gzip=True,
    )
    logger.info("Prometheus /metrics endpoint enabled")

# Security middleware (MUST be added BEFORE CORS so CORS is outermost)
app.add_middleware(SecurityMiddleware)

# Configure CORS (MUST be outermost middleware so all responses get CORS headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)


@app.middleware("http")
async def add_request_metadata(request: Request, call_next) -> Response:
    """Add request ID and timing to all requests."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()

    # Add request_id to request state for logging
    request.state.request_id = request_id

    # Bind request context for all logs in this request
    clear_contextvars()
    bind_contextvars(request_id=request_id, path=request.url.path, method=request.method)

    response = await call_next(request)

    # Add timing and request ID headers
    process_time = time.perf_counter() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    # Log request
    logger.info(
        "Request completed",
        status_code=response.status_code,
        process_time_ms=round(process_time * 1000, 2),
    )

    return response


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": settings.app_name}


@app.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check - verifies all dependencies are available.

    Returns:
        Detailed health status of all components
    """
    from sqlalchemy import text
    from app.database import AsyncSessionLocal

    checks = {"status": "healthy", "checks": {}}
    all_healthy = True

    # Check database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["checks"]["database"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        checks["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    # Check Redis
    try:
        if cache_manager.redis:
            start = time.perf_counter()
            await cache_manager.redis.ping()
            latency = (time.perf_counter() - start) * 1000
            checks["checks"]["redis"] = {"status": "healthy", "latency_ms": round(latency, 2)}
        else:
            checks["checks"]["redis"] = {"status": "not_configured"}
    except Exception as e:
        checks["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    if not all_healthy:
        checks["status"] = "unhealthy"
        return JSONResponse(status_code=503, content=checks)

    return checks


@app.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Liveness check - basic check that the service is running.

    Returns:
        Simple alive status
    """
    return {"status": "alive"}


@app.get("/metrics/cache")
async def cache_stats() -> dict:
    """Get cache statistics.

    Returns:
        Cache hit/miss stats
    """
    return await cache_manager.get_stats()


@app.get("/metrics/gpu")
async def gpu_stats() -> dict:
    """Get GPU metrics summary.

    Returns:
        GPU utilization, memory, temperature stats
    """
    try:
        from app.metrics.gpu_metrics import gpu_metrics

        return gpu_metrics.get_summary()
    except ImportError:
        return {
            "available": False,
            "error": "GPU metrics module not available",
            "device_count": 0,
            "devices": [],
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "device_count": 0,
            "devices": [],
        }


@app.get("/metrics/ai")
async def ai_brain_stats() -> dict:
    """Get AI Brain metrics summary.

    Returns:
        AI Brain queue, circuit breaker, performance stats
    """
    try:
        from app.services.ai_brain_service import get_ai_brain_service

        service = get_ai_brain_service()
        return service.get_resilience_stats()
    except ImportError:
        return {"error": "AI Brain service not available"}
    except Exception as e:
        return {"error": str(e)}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler.

    Args:
        request: Request object
        exc: Exception

    Returns:
        JSON error response
    """
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# Import and include routers
from app.routes import (
    transactions,
    budgets,
    goals,
    predictions,
    advice,
    reports,
    file_import,
    auth,
    ai,
    ml,
    omnibar,
)

app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["budgets"])
app.include_router(goals.router, prefix="/api/goals", tags=["goals"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(advice.router, prefix="/api/advice", tags=["advice"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(file_import.router, prefix="/api", tags=["import-export"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai-brain"])
app.include_router(ml.router, prefix="/api/ml", tags=["ml-models"])
app.include_router(omnibar.router, prefix="/api/omnibar", tags=["omnibar"])
