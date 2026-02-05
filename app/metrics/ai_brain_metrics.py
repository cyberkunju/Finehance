"""AI Brain custom metrics for Prometheus.

This module provides custom metrics for monitoring AI Brain performance,
including request latency, queue depth, confidence scores, and error rates.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Any

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    REGISTRY,
    CollectorRegistry,
)

from app.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# AI Brain Metrics
# =============================================================================


class AIBrainMetrics:
    """Custom Prometheus metrics for AI Brain service.

    Tracks request performance, queue status, confidence scores,
    circuit breaker state, and error rates.
    """

    def __init__(self, registry: CollectorRegistry = REGISTRY):
        """Initialize AI Brain metrics.

        Args:
            registry: Prometheus registry to use
        """
        self.registry = registry

        # -------------------------------------------------------------------------
        # Request Duration Metrics
        # -------------------------------------------------------------------------
        self.request_duration = Histogram(
            "ai_brain_request_duration_seconds",
            "Time spent processing AI Brain requests",
            labelnames=["mode", "status", "fallback"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 75.0, 100.0],
            registry=registry,
        )

        self.request_total = Counter(
            "ai_brain_requests_total",
            "Total number of AI Brain requests",
            labelnames=["mode", "status", "fallback"],
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Queue Metrics
        # -------------------------------------------------------------------------
        self.queue_depth = Gauge(
            "ai_brain_queue_depth",
            "Number of requests waiting for GPU",
            registry=registry,
        )

        self.queue_active = Gauge(
            "ai_brain_queue_active",
            "Number of requests currently being processed",
            registry=registry,
        )

        self.queue_timeout_total = Counter(
            "ai_brain_queue_timeout_total",
            "Total number of queue timeout errors",
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Circuit Breaker Metrics
        # -------------------------------------------------------------------------
        self.circuit_state = Gauge(
            "ai_brain_circuit_state",
            "Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)",
            registry=registry,
        )

        self.circuit_failures = Counter(
            "ai_brain_circuit_failures_total",
            "Total circuit breaker failures",
            registry=registry,
        )

        self.circuit_opens = Counter(
            "ai_brain_circuit_opens_total",
            "Number of times circuit breaker opened",
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Confidence Score Metrics
        # -------------------------------------------------------------------------
        self.confidence_score = Histogram(
            "ai_brain_confidence_score",
            "Distribution of AI response confidence scores",
            labelnames=["mode"],
            buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0],
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Token Metrics
        # -------------------------------------------------------------------------
        self.input_tokens = Histogram(
            "ai_brain_input_tokens",
            "Number of input tokens per request",
            labelnames=["mode"],
            buckets=[50, 100, 250, 500, 1000, 2000, 4000],
            registry=registry,
        )

        self.output_tokens = Histogram(
            "ai_brain_output_tokens",
            "Number of output tokens per response",
            labelnames=["mode"],
            buckets=[50, 100, 250, 500, 1000, 2000],
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Cache Metrics
        # -------------------------------------------------------------------------
        self.cache_hits = Counter(
            "ai_brain_cache_hits_total",
            "Total cache hits for AI responses",
            labelnames=["mode"],
            registry=registry,
        )

        self.cache_misses = Counter(
            "ai_brain_cache_misses_total",
            "Total cache misses for AI responses",
            labelnames=["mode"],
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Error Metrics
        # -------------------------------------------------------------------------
        self.errors_total = Counter(
            "ai_brain_errors_total",
            "Total AI Brain errors by type",
            labelnames=["error_type", "mode"],
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Model Info
        # -------------------------------------------------------------------------
        self.model_info = Info(
            "ai_brain_model",
            "AI Brain model information",
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # Retry Metrics
        # -------------------------------------------------------------------------
        self.retry_attempts = Counter(
            "ai_brain_retry_attempts_total",
            "Total retry attempts",
            labelnames=["mode"],
            registry=registry,
        )

        # -------------------------------------------------------------------------
        # InputGuard / OutputGuard Metrics
        # -------------------------------------------------------------------------
        self.input_blocked = Counter(
            "ai_brain_input_blocked_total",
            "Requests blocked by InputGuard",
            labelnames=["attack_type"],
            registry=registry,
        )

        self.output_filtered = Counter(
            "ai_brain_output_filtered_total",
            "Responses filtered by OutputGuard",
            labelnames=["filter_type"],
            registry=registry,
        )

        self.pii_masked = Counter(
            "ai_brain_pii_masked_total",
            "PII instances masked in responses",
            labelnames=["pii_type"],
            registry=registry,
        )

    def set_model_info(
        self,
        model_name: str,
        model_version: str,
        adapter_name: str = "",
        quantization: str = "4-bit",
    ) -> None:
        """Set AI model information.

        Args:
            model_name: Base model name
            model_version: Model version
            adapter_name: LoRA adapter name (if any)
            quantization: Quantization method
        """
        self.model_info.info(
            {
                "model_name": model_name,
                "model_version": model_version,
                "adapter_name": adapter_name,
                "quantization": quantization,
            }
        )

    @contextmanager
    def track_request(
        self,
        mode: str,
        fallback: bool = False,
    ):
        """Context manager to track AI Brain request metrics.

        Args:
            mode: Request mode (chat, analyze, parse)
            fallback: Whether using fallback response

        Yields:
            None

        Example:
            with ai_metrics.track_request("chat", fallback=False):
                response = await ai_service.chat(message)
        """
        start_time = time.perf_counter()
        status = "success"
        fallback_label = "true" if fallback else "false"

        try:
            yield
        except Exception as e:
            status = "error"
            self.errors_total.labels(
                error_type=type(e).__name__,
                mode=mode,
            ).inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.request_duration.labels(
                mode=mode,
                status=status,
                fallback=fallback_label,
            ).observe(duration)
            self.request_total.labels(
                mode=mode,
                status=status,
                fallback=fallback_label,
            ).inc()

    def record_confidence(self, mode: str, score: float) -> None:
        """Record confidence score for a response.

        Args:
            mode: Request mode
            score: Confidence score (0.0 to 1.0)
        """
        self.confidence_score.labels(mode=mode).observe(score)

    def record_tokens(
        self,
        mode: str,
        input_count: int,
        output_count: int,
    ) -> None:
        """Record token counts for a request.

        Args:
            mode: Request mode
            input_count: Number of input tokens
            output_count: Number of output tokens
        """
        self.input_tokens.labels(mode=mode).observe(input_count)
        self.output_tokens.labels(mode=mode).observe(output_count)

    def update_queue_stats(
        self,
        active: int,
        waiting: int,
    ) -> None:
        """Update queue statistics.

        Args:
            active: Number of active requests
            waiting: Number of waiting requests
        """
        self.queue_active.set(active)
        self.queue_depth.set(waiting)

    def update_circuit_state(self, state: int) -> None:
        """Update circuit breaker state.

        Args:
            state: Circuit state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)
        """
        self.circuit_state.set(state)

    def record_circuit_failure(self) -> None:
        """Record a circuit breaker failure."""
        self.circuit_failures.inc()

    def record_circuit_open(self) -> None:
        """Record circuit breaker opening."""
        self.circuit_opens.inc()

    def record_cache_hit(self, mode: str) -> None:
        """Record a cache hit.

        Args:
            mode: Request mode
        """
        self.cache_hits.labels(mode=mode).inc()

    def record_cache_miss(self, mode: str) -> None:
        """Record a cache miss.

        Args:
            mode: Request mode
        """
        self.cache_misses.labels(mode=mode).inc()

    def record_input_blocked(self, attack_type: str) -> None:
        """Record an input blocked by InputGuard.

        Args:
            attack_type: Type of attack detected
        """
        self.input_blocked.labels(attack_type=attack_type).inc()

    def record_output_filtered(self, filter_type: str) -> None:
        """Record a response filtered by OutputGuard.

        Args:
            filter_type: Type of filter applied
        """
        self.output_filtered.labels(filter_type=filter_type).inc()

    def record_pii_masked(self, pii_type: str) -> None:
        """Record PII masking.

        Args:
            pii_type: Type of PII masked (ssn, credit_card, email, etc.)
        """
        self.pii_masked.labels(pii_type=pii_type).inc()

    def record_queue_timeout(self) -> None:
        """Record a queue timeout."""
        self.queue_timeout_total.inc()


# Singleton instance
ai_metrics = AIBrainMetrics()


# =============================================================================
# Decorator for tracking AI requests
# =============================================================================


def track_ai_request(mode: str):
    """Decorator to track AI request metrics.

    Args:
        mode: Request mode (chat, analyze, parse)

    Returns:
        Decorator function

    Example:
        @track_ai_request("chat")
        async def chat_with_ai(message: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            with ai_metrics.track_request(mode):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Metrics Data Classes
# =============================================================================


@dataclass
class AIBrainMetricsSummary:
    """Summary of AI Brain metrics for reporting."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    fallback_requests: int
    avg_latency_seconds: float
    p95_latency_seconds: float
    p99_latency_seconds: float
    queue_depth: int
    active_requests: int
    circuit_state: str
    cache_hit_rate: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "fallback_requests": self.fallback_requests,
            "avg_latency_seconds": round(self.avg_latency_seconds, 3),
            "p95_latency_seconds": round(self.p95_latency_seconds, 3),
            "p99_latency_seconds": round(self.p99_latency_seconds, 3),
            "queue_depth": self.queue_depth,
            "active_requests": self.active_requests,
            "circuit_state": self.circuit_state,
            "cache_hit_rate": round(self.cache_hit_rate, 3),
        }
