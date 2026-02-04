"""
AI Brain Service - Integration layer for the Financial AI Brain LLM.

This service provides a bridge between the main application and the 
fine-tuned Qwen 2.5-3B model for advanced financial intelligence.

Phase 2 Enhancements:
- Request queue with GPU concurrency control (asyncio.Semaphore)
- Circuit breaker pattern for fault tolerance
- Retry with exponential backoff
- Progressive timeout escalation

Phase 3 Enhancements:
- Prometheus metrics for observability
- Request latency tracking
- Queue depth monitoring
- Error tracking by type
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Callable
from decimal import Decimal
from uuid import UUID
from contextlib import asynccontextmanager

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)

from app.config import settings
from app.logging_config import get_logger
from app.cache import cache_manager

logger = get_logger(__name__)

# Import RAG components (optional - won't fail if not available)
try:
    from app.services.rag_context import (
        RAGContextBuilder,
        get_rag_builder,
        RAGContext,
    )
    from app.services.merchant_database import (
        MerchantDatabase,
        get_merchant_database,
        MerchantInfo,
    )
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.debug("RAG components not available")

# Import metrics (optional - won't fail if not available)
try:
    from app.metrics.ai_brain_metrics import ai_metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    ai_metrics = None
    logger.debug("AI Brain metrics not available")


# =============================================================================
# Circuit Breaker Implementation
# =============================================================================

class CircuitState(IntEnum):
    """Circuit breaker states."""
    CLOSED = 0      # Normal operation
    OPEN = 1        # Failing, reject requests
    HALF_OPEN = 2   # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    state: CircuitState = CircuitState.CLOSED
    state_changed_at: float = field(default_factory=time.time)


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by temporarily blocking requests
    to a failing service.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        name: str = "circuit",
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures to open circuit
            recovery_timeout: Seconds to wait before trying recovery
            half_open_max_calls: Max calls allowed in half-open state
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name
        self._stats = CircuitBreakerStats()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._stats.state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._stats.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._stats.state == CircuitState.OPEN
    
    async def _check_state(self) -> CircuitState:
        """Check and potentially transition state."""
        async with self._lock:
            if self._stats.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._stats.state_changed_at >= self.recovery_timeout:
                    logger.info(
                        f"Circuit {self.name} transitioning to HALF_OPEN",
                        recovery_timeout=self.recovery_timeout,
                    )
                    self._stats.state = CircuitState.HALF_OPEN
                    self._stats.state_changed_at = time.time()
                    self._half_open_calls = 0
            
            return self._stats.state
    
    async def record_success(self):
        """Record a successful call."""
        async with self._lock:
            self._stats.successes += 1
            self._stats.last_success_time = time.time()
            
            if self._stats.state == CircuitState.HALF_OPEN:
                # Recovery successful, close circuit
                logger.info(f"Circuit {self.name} recovered, closing")
                self._stats.state = CircuitState.CLOSED
                self._stats.state_changed_at = time.time()
                self._stats.failures = 0
                if METRICS_AVAILABLE and ai_metrics:
                    ai_metrics.update_circuit_state(CircuitState.CLOSED)
            elif self._stats.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._stats.failures = 0
                self._stats.failures = 0
    
    async def record_failure(self, error: Optional[Exception] = None):
        """Record a failed call."""
        async with self._lock:
            self._stats.failures += 1
            self._stats.last_failure_time = time.time()
            
            # Record metrics
            if METRICS_AVAILABLE and ai_metrics:
                ai_metrics.record_circuit_failure()
            
            if self._stats.state == CircuitState.HALF_OPEN:
                # Recovery failed, reopen circuit
                logger.warning(
                    f"Circuit {self.name} recovery failed, reopening",
                    error=str(error) if error else None,
                )
                self._stats.state = CircuitState.OPEN
                self._stats.state_changed_at = time.time()
                if METRICS_AVAILABLE and ai_metrics:
                    ai_metrics.record_circuit_open()
                    ai_metrics.update_circuit_state(CircuitState.OPEN)
            elif self._stats.state == CircuitState.CLOSED:
                if self._stats.failures >= self.failure_threshold:
                    logger.warning(
                        f"Circuit {self.name} opened due to failures",
                        failures=self._stats.failures,
                        threshold=self.failure_threshold,
                    )
                    self._stats.state = CircuitState.OPEN
                    self._stats.state_changed_at = time.time()
                    if METRICS_AVAILABLE and ai_metrics:
                        ai_metrics.record_circuit_open()
                        ai_metrics.update_circuit_state(CircuitState.OPEN)
    
    async def can_execute(self) -> bool:
        """Check if a call can be executed."""
        state = await self._check_state()
        
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            return False
        else:  # HALF_OPEN
            async with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
    
    @asynccontextmanager
    async def __call__(self):
        """Context manager for circuit breaker."""
        if not await self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit {self.name} is OPEN, request rejected"
            )
        
        try:
            yield
            await self.record_success()
        except Exception as e:
            await self.record_failure(e)
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._stats.state.name,
            "failures": self._stats.failures,
            "successes": self._stats.successes,
            "last_failure": self._stats.last_failure_time,
            "last_success": self._stats.last_success_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# =============================================================================
# Request Queue (GPU Concurrency Control)
# =============================================================================

class RequestQueue:
    """
    GPU request queue with concurrency limiting.
    
    Uses asyncio.Semaphore to limit concurrent GPU requests,
    preventing OOM and ensuring fair resource allocation.
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,
        queue_timeout: float = 30.0,
        name: str = "gpu_queue",
    ):
        """
        Initialize request queue.
        
        Args:
            max_concurrent: Maximum concurrent requests
            queue_timeout: Maximum time to wait in queue
            name: Name for logging
        """
        self.max_concurrent = max_concurrent
        self.queue_timeout = queue_timeout
        self.name = name
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._waiting = 0
        self._active = 0
        self._total_processed = 0
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a slot in the queue."""
        async with self._lock:
            self._waiting += 1
            # Update metrics
            if METRICS_AVAILABLE and ai_metrics:
                ai_metrics.update_queue_stats(self._active, self._waiting)
        
        try:
            # Wait for slot with timeout
            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=self.queue_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Queue {self.name} timeout waiting for slot",
                    waiting=self._waiting,
                    active=self._active,
                )
                if METRICS_AVAILABLE and ai_metrics:
                    ai_metrics.record_queue_timeout()
                raise QueueTimeoutError(
                    f"Timeout waiting for {self.name} slot after {self.queue_timeout}s"
                )
            
            async with self._lock:
                self._waiting -= 1
                self._active += 1
                # Update metrics
                if METRICS_AVAILABLE and ai_metrics:
                    ai_metrics.update_queue_stats(self._active, self._waiting)
            
            logger.debug(
                f"Acquired {self.name} slot",
                active=self._active,
                waiting=self._waiting,
            )
            
            try:
                yield
            finally:
                self._semaphore.release()
                async with self._lock:
                    self._active -= 1
                    self._total_processed += 1
                    # Update metrics
                    if METRICS_AVAILABLE and ai_metrics:
                        ai_metrics.update_queue_stats(self._active, self._waiting)
        except asyncio.TimeoutError:
            async with self._lock:
                self._waiting -= 1
                # Update metrics
                if METRICS_AVAILABLE and ai_metrics:
                    ai_metrics.update_queue_stats(self._active, self._waiting)
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active": self._active,
            "waiting": self._waiting,
            "total_processed": self._total_processed,
            "available_slots": self.max_concurrent - self._active,
        }


class QueueTimeoutError(Exception):
    """Raised when queue wait times out."""
    pass


# =============================================================================
# Timeout Escalation Strategy
# =============================================================================

class TimeoutStrategy:
    """
    Progressive timeout escalation strategy.
    
    Different operations get different timeouts based on expected duration.
    """
    
    # Timeout configurations (in seconds)
    TIMEOUTS = {
        "health_check": 5.0,
        "parse": 15.0,        # Transaction parsing is quick
        "chat": 30.0,         # Chat needs more time
        "analyze": 60.0,      # Analysis is complex
        "cold_start": 90.0,   # First request loads model
    }
    
    def __init__(self):
        self._cold_start_done = False
    
    def get_timeout(self, operation: str, is_retry: bool = False) -> float:
        """
        Get timeout for an operation.
        
        Args:
            operation: Type of operation
            is_retry: Whether this is a retry attempt
            
        Returns:
            Timeout in seconds
        """
        base_timeout = self.TIMEOUTS.get(operation, 30.0)
        
        # Use cold start timeout for first request
        if not self._cold_start_done and operation != "health_check":
            base_timeout = max(base_timeout, self.TIMEOUTS["cold_start"])
        
        # Increase timeout for retries
        if is_retry:
            base_timeout *= 1.5
        
        return base_timeout
    
    def mark_warm(self):
        """Mark that cold start is complete."""
        self._cold_start_done = True


class AIBrainMode(str, Enum):
    """Operating modes for the AI Brain."""
    CHAT = "chat"
    ANALYZE = "analyze"
    PARSE = "parse"
    AUTO = "auto"


@dataclass
class AIBrainResponse:
    """Response from the AI Brain."""
    mode: AIBrainMode
    response: str
    parsed_data: Optional[Dict] = None
    confidence: float = 1.0
    processing_time_ms: float = 0.0
    from_cache: bool = False


class AIBrainService:
    """
    Service for interacting with the Financial AI Brain.
    
    Supports two modes:
    1. HTTP mode: Connects to a separate AI Brain server
    2. Direct mode: Loads model in-process (requires GPU)
    
    Falls back to rule-based responses when AI Brain is unavailable.
    
    Phase 2 Reliability Features:
    - Circuit breaker: Auto-fail on repeated failures (3 failures = 30s cooldown)
    - Request queue: Max 3 concurrent GPU requests to prevent OOM
    - Retry with backoff: Automatic retry with exponential backoff
    - Timeout escalation: Progressive timeouts based on operation type
    """
    
    # Singleton instances for shared state
    _circuit_breaker: Optional[CircuitBreaker] = None
    _request_queue: Optional[RequestQueue] = None
    _timeout_strategy: Optional[TimeoutStrategy] = None
    
    def __init__(
        self,
        mode: str = "http",
        brain_url: Optional[str] = None,
        model_path: Optional[str] = None,
        max_concurrent_requests: int = 3,
        circuit_failure_threshold: int = 3,
        circuit_recovery_timeout: float = 30.0,
    ):
        """
        Initialize AI Brain service.
        
        Args:
            mode: "http" to connect to server, "direct" to load model in-process
            brain_url: URL of the AI Brain server (for HTTP mode)
            model_path: Path to the model (for direct mode)
            max_concurrent_requests: Max concurrent GPU requests (queue limit)
            circuit_failure_threshold: Failures before circuit opens
            circuit_recovery_timeout: Seconds before circuit tries recovery
        """
        self.mode = mode
        self.brain_url = brain_url or getattr(settings, 'ai_brain_url', 'http://localhost:8080')
        self.model_path = model_path or getattr(settings, 'ai_brain_model_path', './ai_brain/models/financial-brain-qlora')
        self._brain = None
        self._http_client = None
        self._available = None
        self._last_check = 0  # Timestamp of last availability check
        self._check_interval = 30  # Retry every 30 seconds
        
        # Initialize reliability components (shared across instances)
        if AIBrainService._circuit_breaker is None:
            AIBrainService._circuit_breaker = CircuitBreaker(
                failure_threshold=circuit_failure_threshold,
                recovery_timeout=circuit_recovery_timeout,
                name="ai_brain",
            )
        
        if AIBrainService._request_queue is None:
            AIBrainService._request_queue = RequestQueue(
                max_concurrent=max_concurrent_requests,
                queue_timeout=30.0,
                name="gpu_queue",
            )
        
        if AIBrainService._timeout_strategy is None:
            AIBrainService._timeout_strategy = TimeoutStrategy()
        
        self.circuit_breaker = AIBrainService._circuit_breaker
        self.request_queue = AIBrainService._request_queue
        self.timeout_strategy = AIBrainService._timeout_strategy
        
    async def _check_availability(self) -> bool:
        """Check if the AI Brain service is available."""
        import time
        current_time = time.time()
        
        # Use cached result if available and not expired
        if self._available is not None and (current_time - self._last_check) < self._check_interval:
            return self._available
            
        self._last_check = current_time
            
        if self.mode == "http":
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.brain_url}/health")
                    self._available = response.status_code == 200
                    if self._available:
                        logger.info("AI Brain HTTP server connected", url=self.brain_url)
            except Exception as e:
                logger.warning("AI Brain HTTP server not available", error=str(e))
                self._available = False
        else:
            # Check if model exists for direct mode
            model_exists = os.path.exists(self.model_path)
            if model_exists:
                try:
                    import torch
                    self._available = torch.cuda.is_available()
                    if not self._available:
                        logger.warning("AI Brain requires GPU but CUDA not available")
                except ImportError:
                    self._available = False
            else:
                logger.warning("AI Brain model not found", path=self.model_path)
                self._available = False
                
        return self._available
    
    async def _get_brain(self):
        """Get or initialize the AI Brain instance (for direct mode)."""
        if self._brain is not None:
            return self._brain
            
        if self.mode != "direct":
            return None
            
        try:
            # Import from ai_brain package
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            from ai_brain.inference.brain_service import FinancialBrain
            
            self._brain = FinancialBrain(model_path=self.model_path)
            self._brain.load_model()
            logger.info("AI Brain loaded successfully in direct mode")
            return self._brain
        except Exception as e:
            logger.error("Failed to load AI Brain", error=str(e))
            return None
    
    async def query(
        self,
        query: str,
        mode: AIBrainMode = AIBrainMode.AUTO,
        context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
        use_cache: bool = True,
    ) -> AIBrainResponse:
        """
        Query the AI Brain.
        
        Args:
            query: User query or transaction description
            mode: Operating mode (chat, analyze, parse, auto)
            context: User financial context
            conversation_history: Previous conversation turns
            use_cache: Whether to use cached responses
            
        Returns:
            AIBrainResponse with the result
        """
        operation = mode.value if mode != AIBrainMode.AUTO else "chat"
        
        # Check cache first
        if use_cache and mode != AIBrainMode.CHAT:
            cache_key = f"ai_brain:{mode.value}:{hash(query)}"
            cached = await cache_manager.get(cache_key)
            if cached:
                # Record cache hit
                if METRICS_AVAILABLE and ai_metrics:
                    ai_metrics.record_cache_hit(operation)
                return AIBrainResponse(
                    mode=AIBrainMode(cached["mode"]),
                    response=cached["response"],
                    parsed_data=cached.get("parsed_data"),
                    confidence=cached.get("confidence", 1.0),
                    processing_time_ms=0,
                    from_cache=True,
                )
            else:
                # Record cache miss
                if METRICS_AVAILABLE and ai_metrics:
                    ai_metrics.record_cache_miss(operation)
        
        # Check availability
        is_available = await self._check_availability()
        
        if not is_available:
            # Fall back to rule-based response
            return await self._fallback_response(query, mode, context)
        
        # Check circuit breaker before attempting
        if self.circuit_breaker.is_open:
            logger.warning(
                "Circuit breaker is OPEN, using fallback",
                circuit_stats=self.circuit_breaker.get_stats(),
            )
            return await self._fallback_response(query, mode, context)
        
        try:
            if self.mode == "http":
                result = await self._query_http_with_resilience(query, mode, context, conversation_history)
            else:
                result = await self._query_direct(query, mode, context, conversation_history)
            
            # Mark model as warm after first successful request
            self.timeout_strategy.mark_warm()
            
            # Cache non-chat responses
            if use_cache and mode != AIBrainMode.CHAT:
                await cache_manager.set(
                    cache_key,
                    {
                        "mode": result.mode.value,
                        "response": result.response,
                        "parsed_data": result.parsed_data,
                        "confidence": result.confidence,
                    },
                    expire=3600,  # 1 hour cache
                )
            
            return result
        
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker prevented request")
            return await self._fallback_response(query, mode, context)
        
        except QueueTimeoutError:
            logger.warning("Request queue timeout, too many concurrent requests")
            return await self._fallback_response(query, mode, context)
            
        except Exception as e:
            logger.error("AI Brain query failed", error=str(e))
            return await self._fallback_response(query, mode, context)
    
    async def _query_http_with_resilience(
        self,
        query: str,
        mode: AIBrainMode,
        context: Optional[Dict],
        conversation_history: Optional[List[Dict]],
    ) -> AIBrainResponse:
        """
        Query via HTTP API with resilience patterns.
        
        Applies:
        - Request queue (concurrency limiting)
        - Circuit breaker (fault isolation)
        - Retry with exponential backoff
        - Timeout escalation
        - Prometheus metrics
        """
        operation = mode.value if mode != AIBrainMode.AUTO else "chat"
        timeout = self.timeout_strategy.get_timeout(operation)
        start_time = time.perf_counter()
        
        # Use request queue to limit concurrent GPU requests
        async with self.request_queue.acquire():
            # Use circuit breaker for fault isolation
            async with self.circuit_breaker():
                try:
                    result = await self._query_http_with_retry(
                        query, mode, context, conversation_history, timeout
                    )
                    
                    # Record successful request metrics
                    if METRICS_AVAILABLE and ai_metrics:
                        duration = time.perf_counter() - start_time
                        ai_metrics.request_duration.labels(
                            mode=operation,
                            status="success",
                            fallback="false",
                        ).observe(duration)
                        ai_metrics.request_total.labels(
                            mode=operation,
                            status="success",
                            fallback="false",
                        ).inc()
                        ai_metrics.record_confidence(operation, result.confidence)
                    
                    return result
                    
                except Exception as e:
                    # Record failed request metrics
                    if METRICS_AVAILABLE and ai_metrics:
                        duration = time.perf_counter() - start_time
                        ai_metrics.request_duration.labels(
                            mode=operation,
                            status="error",
                            fallback="false",
                        ).observe(duration)
                        ai_metrics.request_total.labels(
                            mode=operation,
                            status="error",
                            fallback="false",
                        ).inc()
                        ai_metrics.errors_total.labels(
                            error_type=type(e).__name__,
                            mode=operation,
                        ).inc()
                    raise
    
    async def _query_http_with_retry(
        self,
        query: str,
        mode: AIBrainMode,
        context: Optional[Dict],
        conversation_history: Optional[List[Dict]],
        timeout: float,
        max_retries: int = 2,
    ) -> AIBrainResponse:
        """Execute HTTP query with retry logic."""
        import httpx
        
        last_error = None
        operation = mode.value if mode != AIBrainMode.AUTO else "chat"
        
        for attempt in range(max_retries + 1):
            try:
                # Increase timeout for retries
                current_timeout = timeout * (1.5 ** attempt)
                
                logger.debug(
                    f"AI Brain HTTP request attempt {attempt + 1}",
                    timeout=current_timeout,
                    mode=mode.value,
                )
                
                async with httpx.AsyncClient(timeout=current_timeout) as client:
                    response = await client.post(
                        f"{self.brain_url}/query",
                        json={
                            "query": query,
                            "mode": mode.value,
                            "context": context,
                            "conversation_history": conversation_history,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    return AIBrainResponse(
                        mode=AIBrainMode(data["mode"]),
                        response=data["response"],
                        parsed_data=data.get("parsed_data"),
                        confidence=data.get("confidence", 1.0),
                        processing_time_ms=data.get("processing_time_ms", 0),
                    )
                    
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s...
                    logger.warning(
                        f"AI Brain request failed, retrying in {wait_time}s",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                    )
                    # Record retry attempt
                    if METRICS_AVAILABLE and ai_metrics:
                        ai_metrics.retry_attempts.labels(mode=operation).inc()
                    await asyncio.sleep(wait_time)
                continue
                
            except httpx.HTTPStatusError as e:
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise
                last_error = e
                if attempt < max_retries:
                    # Record retry attempt
                    if METRICS_AVAILABLE and ai_metrics:
                        ai_metrics.retry_attempts.labels(mode=operation).inc()
                    await asyncio.sleep(1)
                continue
        
        # All retries exhausted
        raise last_error or RuntimeError("AI Brain request failed after retries")
    
    async def _query_http(
        self,
        query: str,
        mode: AIBrainMode,
        context: Optional[Dict],
        conversation_history: Optional[List[Dict]],
    ) -> AIBrainResponse:
        """Query via HTTP API (legacy, without resilience - use _query_http_with_resilience)."""
        import httpx
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.brain_url}/query",
                json={
                    "query": query,
                    "mode": mode.value,
                    "context": context,
                    "conversation_history": conversation_history,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            return AIBrainResponse(
                mode=AIBrainMode(data["mode"]),
                response=data["response"],
                parsed_data=data.get("parsed_data"),
                confidence=data.get("confidence", 1.0),
                processing_time_ms=data.get("processing_time_ms", 0),
            )
    
    async def _query_direct(
        self,
        query: str,
        mode: AIBrainMode,
        context: Optional[Dict],
        conversation_history: Optional[List[Dict]],
    ) -> AIBrainResponse:
        """Query directly using loaded model."""
        brain = await self._get_brain()
        if not brain:
            raise RuntimeError("AI Brain not loaded")
        
        # Map mode
        from ai_brain.inference.brain_service import BrainMode
        mode_map = {
            AIBrainMode.CHAT: BrainMode.CHAT,
            AIBrainMode.ANALYZE: BrainMode.ANALYZE,
            AIBrainMode.PARSE: BrainMode.PARSE,
            AIBrainMode.AUTO: BrainMode.AUTO,
        }
        
        result = await brain.generate_async(
            query=query,
            mode=mode_map[mode],
            context=context,
            conversation_history=conversation_history,
        )
        
        return AIBrainResponse(
            mode=AIBrainMode(result.mode.value),
            response=result.response,
            parsed_data=result.parsed_data,
            confidence=result.confidence,
            processing_time_ms=result.processing_time_ms,
        )
    
    async def _fallback_response(
        self,
        query: str,
        mode: AIBrainMode,
        context: Optional[Dict],
    ) -> AIBrainResponse:
        """Generate rule-based fallback response when AI Brain is unavailable."""
        logger.info("Using fallback response (AI Brain unavailable)")
        
        # Record fallback metrics
        operation = mode.value if mode != AIBrainMode.AUTO else "chat"
        if METRICS_AVAILABLE and ai_metrics:
            ai_metrics.request_total.labels(
                mode=operation,
                status="success",
                fallback="true",
            ).inc()
        
        if mode == AIBrainMode.PARSE:
            # Use regex-based parsing for transactions
            parsed = self._parse_transaction_fallback(query)
            return AIBrainResponse(
                mode=AIBrainMode.PARSE,
                response=f"Parsed transaction: {parsed.get('merchant', 'Unknown')}",
                parsed_data=parsed,
                confidence=0.6,
            )
        
        elif mode == AIBrainMode.ANALYZE:
            return AIBrainResponse(
                mode=AIBrainMode.ANALYZE,
                response=self._generate_analysis_fallback(context),
                confidence=0.5,
            )
        
        else:
            return AIBrainResponse(
                mode=AIBrainMode.CHAT,
                response="I can help you manage your finances. Ask me about budgeting, saving, or analyzing your spending patterns.",
                confidence=0.5,
            )
    
    def _parse_transaction_fallback(self, description: str) -> Dict:
        """
        Parse transaction using RAG merchant database and regex patterns.
        
        Prioritizes merchant database lookup for high accuracy,
        falls back to keyword matching for unknown merchants.
        """
        import re
        
        # First, try RAG merchant database lookup (most accurate)
        if RAG_AVAILABLE:
            try:
                merchant_db = get_merchant_database()
                merchant_info = merchant_db.lookup(description)
                
                if merchant_info:
                    logger.debug(
                        f"Fallback using merchant DB: {merchant_info.canonical_name}",
                        category=merchant_info.category,
                        match_score=merchant_info.match_score,
                    )
                    return {
                        "merchant": merchant_info.canonical_name,
                        "category": merchant_info.category,
                        "subcategory": merchant_info.subcategory,
                        "merchant_type": "online" if "online" in (merchant_info.subcategory or "").lower() else "retail",
                        "is_recurring": merchant_info.is_recurring,
                        "confidence": min(0.9, merchant_info.match_score + 0.2),  # High confidence from DB
                        "source": "merchant_database",
                    }
            except Exception as e:
                logger.warning(f"Merchant DB lookup failed in fallback: {e}")
        
        # Fall back to keyword-based matching
        description_upper = description.upper()
        
        # Common merchant patterns
        category_keywords = {
            "Groceries": ["WHOLEFDS", "WHOLE FOODS", "TRADER JOE", "COSTCO", "SAFEWAY", "KROGER", "PUBLIX", "ALDI", "WEGMANS", "HEB", "FOOD LION", "GROCERY"],
            "Fast Food": ["MCDONALD", "BURGER KING", "WENDY", "TACO BELL", "CHICK-FIL", "CHIPOTLE", "SUBWAY", "DOMINO", "PIZZA HUT", "KFC", "POPEYE"],
            "Coffee & Beverages": ["STARBUCKS", "DUNKIN", "PEET", "DUTCH BROS", "COFFEE"],
            "Food & Dining": ["RESTAURANT", "CAFE", "BISTRO", "GRILL", "KITCHEN", "DINER"],
            "Shopping & Retail": ["AMAZON", "AMZN", "WALMART", "WMT", "TARGET", "TGT", "BESTBUY", "STORE", "SHOP", "MARKET"],
            "Transportation": ["UBER", "LYFT", "PARKING", "TRANSIT", "METRO"],
            "Gas & Fuel": ["SHELL", "CHEVRON", "EXXON", "MOBIL", "BP", "ARCO", "GAS", "FUEL", "76"],
            "Entertainment": ["NETFLIX", "SPOTIFY", "MOVIE", "GAME", "STEAM", "PLAYSTATION", "XBOX", "AMC", "REGAL"],
            "Subscriptions": ["SUBSCRIPTION", "MONTHLY", "PREMIUM", "MEMBERSHIP", "SPOTIFY", "NETFLIX", "HULU", "DISNEY"],
            "Bills & Utilities": ["ELECTRIC", "WATER", "GAS", "INTERNET", "PHONE", "UTILITY", "AT&T", "VERIZON", "COMCAST", "XFINITY"],
            "Healthcare": ["PHARMACY", "DOCTOR", "MEDICAL", "HOSPITAL", "CLINIC", "CVS", "WALGREEN"],
            "Food Delivery": ["DOORDASH", "GRUBHUB", "UBEREATS", "POSTMATES", "INSTACART"],
        }
        
        detected_category = "Other"
        for category, keywords in category_keywords.items():
            if any(kw in description_upper for kw in keywords):
                detected_category = category
                break
        
        # Extract merchant name (improved)
        # Remove common noise patterns
        clean_desc = re.sub(r'\s*#?\d{4,}.*$', '', description)  # Remove store numbers
        clean_desc = re.sub(r'\s+[A-Z]{2}\s+\d{5}', '', clean_desc)  # Remove city/state/zip
        clean_desc = re.sub(r'\*[A-Z0-9]+', '', clean_desc)  # Remove reference codes
        merchant = clean_desc.strip().split()[0] if clean_desc.strip() else "Unknown"
        
        # Check for recurring patterns
        is_recurring = any(kw in description_upper for kw in ["MONTHLY", "SUBSCRIPTION", "RECURRING", "AUTO-PAY", "NETFLIX", "SPOTIFY", "HULU"])
        
        return {
            "merchant": merchant.title(),
            "category": detected_category,
            "merchant_type": "online" if any(kw in description_upper for kw in ["ONLINE", "WWW", ".COM", "AMZN"]) else "retail",
            "is_recurring": is_recurring,
            "confidence": 0.6,
            "source": "keyword_matching",
        }
    
    def _generate_analysis_fallback(self, context: Optional[Dict]) -> str:
        """Generate basic analysis from context."""
        if not context:
            return "Please provide your financial data for analysis."
        
        parts = []
        
        if "monthly_income" in context:
            parts.append(f"Your monthly income is ${context['monthly_income']:,.2f}.")
        
        if "spending" in context:
            total_spending = sum(context["spending"].values())
            top_categories = sorted(context["spending"].items(), key=lambda x: x[1], reverse=True)[:3]
            parts.append(f"Your total monthly spending is ${total_spending:,.2f}.")
            parts.append(f"Top spending categories: {', '.join(f'{cat} (${amt:,.2f})' for cat, amt in top_categories)}.")
        
        if "goals" in context:
            parts.append(f"You have {len(context['goals'])} active goals.")
        
        return " ".join(parts) if parts else "No analysis data available."
    
    async def chat(
        self,
        message: str,
        context: Optional[Dict] = None,
        history: Optional[List[Dict]] = None,
    ) -> AIBrainResponse:
        """
        Chat with the AI Brain with RAG-enhanced context.
        
        Uses RAG to ground responses in user's actual financial data.
        """
        # Build enriched context using RAG
        enriched_context = context or {}
        
        if RAG_AVAILABLE and context:
            try:
                rag_builder = get_rag_builder()
                rag_context = rag_builder.build_chat_context(
                    query=message,
                    user_context=context,
                )
                rag_context_str = rag_builder.format_for_chat_prompt(rag_context)
                
                enriched_context = {
                    **context,
                    "rag_context": rag_context_str,
                }
                
                logger.debug("RAG context built for chat")
            except Exception as e:
                logger.warning(f"RAG context building failed for chat: {e}")
        
        return await self.query(
            query=message,
            mode=AIBrainMode.CHAT,
            context=enriched_context,
            conversation_history=history,
            use_cache=False,  # Don't cache chat responses
        )
    
    async def analyze(
        self,
        request: str,
        context: Dict,
    ) -> AIBrainResponse:
        """Request financial analysis."""
        return await self.query(
            query=request,
            mode=AIBrainMode.ANALYZE,
            context=context,
        )
    
    async def parse_transaction(
        self,
        description: str,
        user_context: Optional[Dict] = None,
    ) -> AIBrainResponse:
        """
        Parse a transaction description with RAG enrichment.
        
        Uses the merchant database and normalizer to enrich the prompt
        before sending to the AI Brain, dramatically improving accuracy.
        """
        # Build enriched context using RAG
        enriched_context = None
        rag_context_str = None
        
        if RAG_AVAILABLE:
            try:
                rag_builder = get_rag_builder()
                rag_context = rag_builder.build_parse_context(
                    raw_transaction=description,
                    user_context=user_context,
                )
                rag_context_str = rag_builder.format_for_parse_prompt(rag_context)
                
                # Include RAG context in the context dict sent to AI Brain
                enriched_context = {
                    "rag_context": rag_context_str,
                    "merchant_hint": rag_context.merchant_info.canonical_name if rag_context.merchant_info else None,
                    "category_hint": rag_context.category_hint,
                    "context_confidence": rag_context.context_confidence,
                }
                
                logger.debug(
                    "RAG context built for transaction",
                    merchant_found=rag_context.merchant_info is not None,
                    category_hint=rag_context.category_hint,
                )
            except Exception as e:
                logger.warning(f"RAG context building failed: {e}")
        
        # Query AI Brain with enriched context
        result = await self.query(
            query=description,
            mode=AIBrainMode.PARSE,
            context=enriched_context,
        )
        
        # Post-process: Apply merchant database corrections if AI missed them
        if RAG_AVAILABLE and result.parsed_data:
            try:
                merchant_db = get_merchant_database()
                merchant_info = merchant_db.lookup(description)
                
                if merchant_info:
                    # Trust database over AI for known merchants
                    ai_category = result.parsed_data.get("category", "")
                    db_category = merchant_info.category
                    
                    if ai_category != db_category:
                        logger.info(
                            f"RAG correction: {ai_category} -> {db_category}",
                            merchant=merchant_info.canonical_name,
                        )
                        result.parsed_data["category"] = db_category
                        result.parsed_data["subcategory"] = merchant_info.subcategory
                        result.parsed_data["merchant"] = merchant_info.canonical_name
                        result.parsed_data["rag_corrected"] = True
                    
                    # Always use canonical merchant name
                    if merchant_info.canonical_name:
                        result.parsed_data["merchant"] = merchant_info.canonical_name
                    
                    # Add recurring info from database
                    if merchant_info.is_recurring:
                        result.parsed_data["is_recurring"] = True
                        
            except Exception as e:
                logger.warning(f"RAG post-processing failed: {e}")
        
        return result
    
    async def get_smart_advice(
        self,
        user_context: Dict,
        recent_transactions: List[Dict],
        goals: List[Dict],
    ) -> str:
        """Get personalized financial advice using AI Brain."""
        # Build comprehensive context
        context = {
            **user_context,
            "recent_transactions": recent_transactions[-20:],  # Last 20 transactions
            "goals": goals,
        }
        
        prompt = """Based on my financial situation, provide 3-5 specific, actionable recommendations to improve my finances. 
        Focus on:
        1. Immediate actions I can take
        2. Spending patterns to address
        3. Progress towards my goals
        4. Opportunities for savings"""
        
        result = await self.query(
            query=prompt,
            mode=AIBrainMode.ANALYZE,
            context=context,
        )
        
        return result.response
    
    def get_resilience_stats(self) -> Dict[str, Any]:
        """
        Get statistics about resilience components.
        
        Returns:
            Dict with circuit breaker and queue stats
        """
        return {
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "request_queue": self.request_queue.get_stats(),
            "timeout_strategy": {
                "cold_start_done": self.timeout_strategy._cold_start_done,
                "timeouts": self.timeout_strategy.TIMEOUTS,
            },
        }
    
    async def reset_circuit_breaker(self):
        """Manually reset the circuit breaker (for admin use)."""
        async with self.circuit_breaker._lock:
            self.circuit_breaker._stats = CircuitBreakerStats()
            logger.info("Circuit breaker manually reset")


# Global singleton instance
_ai_brain_service: Optional[AIBrainService] = None


def get_ai_brain_service() -> AIBrainService:
    """Get or create the AI Brain service singleton."""
    global _ai_brain_service
    if _ai_brain_service is None:
        mode = getattr(settings, 'ai_brain_mode', 'http')
        _ai_brain_service = AIBrainService(mode=mode)
    return _ai_brain_service


async def get_ai_brain() -> AIBrainService:
    """FastAPI dependency for AI Brain service."""
    return get_ai_brain_service()
