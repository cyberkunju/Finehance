"""
Comprehensive tests for AIBrainService - Phase 2 Reliability & Resilience.

Tests cover:
- Circuit breaker pattern
- Request queue (concurrency control)
- Retry with backoff
- Timeout escalation
- Fallback behavior
- Integration tests
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_brain_service import (
    AIBrainService,
    AIBrainMode,
    AIBrainResponse,
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    RequestQueue,
    QueueTimeoutError,
    TimeoutStrategy,
)


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreaker:
    """Tests for circuit breaker pattern."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Fresh circuit breaker for each test."""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short for testing
            half_open_max_calls=1,
            name="test_circuit",
        )
    
    @pytest.mark.asyncio
    async def test_starts_closed(self, circuit_breaker):
        """Circuit breaker should start in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.is_closed
        assert not circuit_breaker.is_open
    
    @pytest.mark.asyncio
    async def test_stays_closed_on_success(self, circuit_breaker):
        """Circuit should stay closed on successful calls."""
        await circuit_breaker.record_success()
        await circuit_breaker.record_success()
        await circuit_breaker.record_success()
        
        assert circuit_breaker.is_closed
        stats = circuit_breaker.get_stats()
        assert stats["successes"] == 3
        assert stats["failures"] == 0
    
    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self, circuit_breaker):
        """Circuit should open after failure threshold is reached."""
        # Record failures up to threshold
        await circuit_breaker.record_failure(Exception("Test error 1"))
        assert circuit_breaker.is_closed  # Not yet
        
        await circuit_breaker.record_failure(Exception("Test error 2"))
        assert circuit_breaker.is_closed  # Not yet
        
        await circuit_breaker.record_failure(Exception("Test error 3"))
        assert circuit_breaker.is_open  # Now open!
        
        stats = circuit_breaker.get_stats()
        assert stats["state"] == "OPEN"
        assert stats["failures"] == 3
    
    @pytest.mark.asyncio
    async def test_rejects_when_open(self, circuit_breaker):
        """Circuit should reject calls when open."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()
        
        assert circuit_breaker.is_open
        assert not await circuit_breaker.can_execute()
    
    @pytest.mark.asyncio
    async def test_transitions_to_half_open(self, circuit_breaker):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()
        
        assert circuit_breaker.is_open
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Check state transition
        state = await circuit_breaker._check_state()
        assert state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_closes_on_half_open_success(self, circuit_breaker):
        """Circuit should close after successful call in HALF_OPEN state."""
        # Open and wait for half-open
        for _ in range(3):
            await circuit_breaker.record_failure()
        await asyncio.sleep(1.1)
        await circuit_breaker._check_state()
        
        # Record success in half-open
        await circuit_breaker.record_success()
        
        assert circuit_breaker.is_closed
    
    @pytest.mark.asyncio
    async def test_reopens_on_half_open_failure(self, circuit_breaker):
        """Circuit should reopen after failure in HALF_OPEN state."""
        # Open and wait for half-open
        for _ in range(3):
            await circuit_breaker.record_failure()
        await asyncio.sleep(1.1)
        await circuit_breaker._check_state()
        
        # Allow one call in half-open
        can_execute = await circuit_breaker.can_execute()
        assert can_execute
        
        # Record failure
        await circuit_breaker.record_failure()
        
        assert circuit_breaker.is_open
    
    @pytest.mark.asyncio
    async def test_context_manager_success(self, circuit_breaker):
        """Context manager should record success on normal exit."""
        async with circuit_breaker():
            pass  # Success
        
        stats = circuit_breaker.get_stats()
        assert stats["successes"] == 1
    
    @pytest.mark.asyncio
    async def test_context_manager_failure(self, circuit_breaker):
        """Context manager should record failure on exception."""
        with pytest.raises(ValueError):
            async with circuit_breaker():
                raise ValueError("Test error")
        
        stats = circuit_breaker.get_stats()
        assert stats["failures"] == 1
    
    @pytest.mark.asyncio
    async def test_context_manager_raises_when_open(self, circuit_breaker):
        """Context manager should raise CircuitBreakerOpenError when open."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()
        
        with pytest.raises(CircuitBreakerOpenError):
            async with circuit_breaker():
                pass
    
    @pytest.mark.asyncio
    async def test_resets_failures_on_success(self, circuit_breaker):
        """Failure count should reset on success."""
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()
        
        stats = circuit_breaker.get_stats()
        assert stats["failures"] == 2
        
        await circuit_breaker.record_success()
        
        stats = circuit_breaker.get_stats()
        assert stats["failures"] == 0


# =============================================================================
# Request Queue Tests
# =============================================================================

class TestRequestQueue:
    """Tests for GPU request queue (concurrency control)."""
    
    @pytest.fixture
    def request_queue(self):
        """Fresh request queue for each test."""
        return RequestQueue(
            max_concurrent=2,
            queue_timeout=1.0,  # Short for testing
            name="test_queue",
        )
    
    @pytest.mark.asyncio
    async def test_allows_within_limit(self, request_queue):
        """Queue should allow requests within concurrency limit."""
        async with request_queue.acquire():
            stats = request_queue.get_stats()
            assert stats["active"] == 1
            assert stats["available_slots"] == 1
    
    @pytest.mark.asyncio
    async def test_releases_on_completion(self, request_queue):
        """Queue should release slot when request completes."""
        async with request_queue.acquire():
            pass
        
        stats = request_queue.get_stats()
        assert stats["active"] == 0
        assert stats["available_slots"] == 2
        assert stats["total_processed"] == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_within_limit(self, request_queue):
        """Multiple concurrent requests within limit should work."""
        results = []
        
        async def task(id):
            async with request_queue.acquire():
                await asyncio.sleep(0.1)
                results.append(id)
        
        await asyncio.gather(task(1), task(2))
        
        assert len(results) == 2
        stats = request_queue.get_stats()
        assert stats["total_processed"] == 2
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, request_queue):
        """Requests over limit should queue."""
        order = []
        
        async def slow_task():
            async with request_queue.acquire():
                order.append("start")
                await asyncio.sleep(0.3)
                order.append("end")
        
        async def quick_task():
            await asyncio.sleep(0.1)  # Wait a bit
            async with request_queue.acquire():
                order.append("quick")
        
        # Start 2 slow tasks (max concurrent)
        task1 = asyncio.create_task(slow_task())
        task2 = asyncio.create_task(slow_task())
        
        # Start a third task - should wait
        task3 = asyncio.create_task(quick_task())
        
        await asyncio.gather(task1, task2, task3)
        
        # Quick task should have waited for a slot
        assert "quick" in order
    
    @pytest.mark.asyncio
    async def test_timeout_on_queue_wait(self, request_queue):
        """Should raise QueueTimeoutError if wait times out."""
        # Fill the queue
        async def long_task():
            async with request_queue.acquire():
                await asyncio.sleep(2)  # Longer than timeout
        
        # Start max concurrent tasks
        task1 = asyncio.create_task(long_task())
        task2 = asyncio.create_task(long_task())
        
        # Give tasks time to acquire
        await asyncio.sleep(0.1)
        
        # Third task should timeout
        with pytest.raises(QueueTimeoutError):
            async with request_queue.acquire():
                pass
        
        # Cancel long tasks
        task1.cancel()
        task2.cancel()
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self, request_queue):
        """Stats should be accurately tracked."""
        async with request_queue.acquire():
            stats = request_queue.get_stats()
            assert stats["active"] == 1
            assert stats["waiting"] == 0
        
        stats = request_queue.get_stats()
        assert stats["active"] == 0
        assert stats["total_processed"] == 1


# =============================================================================
# Timeout Strategy Tests
# =============================================================================

class TestTimeoutStrategy:
    """Tests for timeout escalation strategy."""
    
    @pytest.fixture
    def timeout_strategy(self):
        """Fresh timeout strategy for each test."""
        return TimeoutStrategy()
    
    def test_health_check_timeout(self, timeout_strategy):
        """Health check should have short timeout."""
        timeout = timeout_strategy.get_timeout("health_check")
        assert timeout == 5.0
    
    def test_parse_timeout(self, timeout_strategy):
        """Parse operations should have medium timeout (or cold start if not warm)."""
        # Before warm, cold start timeout applies
        timeout = timeout_strategy.get_timeout("parse")
        assert timeout == 90.0  # cold_start timeout when not warm
        
        # After warm, should use normal parse timeout
        timeout_strategy.mark_warm()
        timeout = timeout_strategy.get_timeout("parse")
        assert timeout == 15.0
    
    def test_chat_timeout(self, timeout_strategy):
        """Chat operations should have longer timeout."""
        timeout = timeout_strategy.get_timeout("chat")
        assert timeout == 30.0 or timeout == 90.0  # 90 if cold start
    
    def test_analyze_timeout(self, timeout_strategy):
        """Analyze operations should have longest timeout."""
        timeout = timeout_strategy.get_timeout("analyze")
        assert timeout == 60.0 or timeout == 90.0  # 90 if cold start
    
    def test_cold_start_timeout(self, timeout_strategy):
        """Cold start should use extended timeout."""
        # Before warm, should use cold start timeout
        timeout = timeout_strategy.get_timeout("chat")
        assert timeout == 90.0  # cold_start timeout
    
    def test_warm_reduces_timeout(self, timeout_strategy):
        """After marking warm, should use normal timeout."""
        timeout_strategy.mark_warm()
        timeout = timeout_strategy.get_timeout("chat")
        assert timeout == 30.0  # Normal chat timeout
    
    def test_retry_increases_timeout(self, timeout_strategy):
        """Retry should increase timeout by 1.5x."""
        timeout_strategy.mark_warm()
        normal = timeout_strategy.get_timeout("chat")
        retry = timeout_strategy.get_timeout("chat", is_retry=True)
        assert retry == normal * 1.5
    
    def test_unknown_operation_default(self, timeout_strategy):
        """Unknown operations should get default timeout."""
        timeout_strategy.mark_warm()
        timeout = timeout_strategy.get_timeout("unknown_operation")
        assert timeout == 30.0  # Default


# =============================================================================
# AIBrainService Tests
# =============================================================================

class TestAIBrainService:
    """Integration tests for AIBrainService with resilience features."""
    
    @pytest.fixture
    def service(self):
        """Fresh service for each test (reset singleton state)."""
        # Reset singleton state
        AIBrainService._circuit_breaker = None
        AIBrainService._request_queue = None
        AIBrainService._timeout_strategy = None
        
        return AIBrainService(
            mode="http",
            brain_url="http://localhost:8080",
            max_concurrent_requests=3,
            circuit_failure_threshold=3,
            circuit_recovery_timeout=30.0,
        )
    
    def test_initialization(self, service):
        """Service should initialize with resilience components."""
        assert service.circuit_breaker is not None
        assert service.request_queue is not None
        assert service.timeout_strategy is not None
    
    def test_get_resilience_stats(self, service):
        """Should return resilience statistics."""
        stats = service.get_resilience_stats()
        
        assert "circuit_breaker" in stats
        assert "request_queue" in stats
        assert "timeout_strategy" in stats
        
        assert stats["circuit_breaker"]["state"] == "CLOSED"
        assert stats["request_queue"]["max_concurrent"] == 3
    
    @pytest.mark.asyncio
    async def test_fallback_on_circuit_open(self, service):
        """Should use fallback when circuit is open."""
        # Open the circuit
        for _ in range(3):
            await service.circuit_breaker.record_failure()
        
        assert service.circuit_breaker.is_open
        
        # Query should return fallback
        result = await service.query("Hello", mode=AIBrainMode.CHAT)
        
        # Should get fallback response (confidence 0.5)
        assert result.confidence == 0.5
    
    @pytest.mark.asyncio
    async def test_fallback_response_parse_mode(self, service):
        """Fallback should work for parse mode."""
        service._available = False  # Force fallback
        
        result = await service._fallback_response(
            "STARBUCKS COFFEE",
            AIBrainMode.PARSE,
            None,
        )
        
        assert result.mode == AIBrainMode.PARSE
        assert result.parsed_data is not None
        assert result.confidence == 0.6  # Fallback confidence
    
    @pytest.mark.asyncio
    async def test_fallback_response_analyze_mode(self, service):
        """Fallback should work for analyze mode."""
        context = {
            "monthly_income": 5000.00,
            "spending": {"Food": 500, "Transport": 200},
        }
        
        result = await service._fallback_response(
            "Analyze my finances",
            AIBrainMode.ANALYZE,
            context,
        )
        
        assert result.mode == AIBrainMode.ANALYZE
        assert "5,000" in result.response  # Income mentioned
        assert result.confidence == 0.5
    
    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self, service):
        """Should be able to manually reset circuit breaker."""
        # Open the circuit
        for _ in range(3):
            await service.circuit_breaker.record_failure()
        
        assert service.circuit_breaker.is_open
        
        # Reset
        await service.reset_circuit_breaker()
        
        assert service.circuit_breaker.is_closed
    
    @pytest.mark.asyncio
    async def test_parse_transaction_fallback(self, service):
        """Transaction parsing fallback should detect categories."""
        service._available = False
        
        test_cases = [
            ("STARBUCKS COFFEE", "Food & Dining"),
            ("AMAZON.COM", "Shopping & Retail"),
            ("UBER RIDE", "Transportation"),
            ("NETFLIX SUBSCRIPTION", "Entertainment"),
        ]
        
        for description, expected_category in test_cases:
            result = await service.parse_transaction(description)
            assert result.parsed_data["category"] == expected_category, \
                f"Expected {expected_category} for {description}"


# =============================================================================
# Integration Tests (requires running AI Brain)
# =============================================================================

@pytest.mark.integration
class TestAIBrainServiceIntegration:
    """Integration tests that require running AI Brain service."""
    
    @pytest.fixture
    def service(self):
        """Service configured for integration tests."""
        # Reset singleton state
        AIBrainService._circuit_breaker = None
        AIBrainService._request_queue = None  
        AIBrainService._timeout_strategy = None
        
        return AIBrainService(
            mode="http",
            brain_url="http://localhost:8080",
        )
    
    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Should check availability via health endpoint."""
        is_available = await service._check_availability()
        # This will pass or fail depending on whether AI Brain is running
        assert isinstance(is_available, bool)
    
    @pytest.mark.asyncio
    async def test_chat_request(self, service):
        """Should make chat request to AI Brain."""
        result = await service.chat("What is budgeting?")
        
        assert result.mode == AIBrainMode.CHAT
        assert len(result.response) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
