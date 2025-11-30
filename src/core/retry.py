"""
Enterprise Retry Logic
Exponential backoff with jitter for API calls and file operations
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, TypeVar, Optional, Tuple, Type, Any
from dataclasses import dataclass

from .exceptions import APIError, TradingError

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.25
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        APIError,
    )


def calculate_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    Calculate delay with exponential backoff and optional jitter

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    # Exponential backoff
    delay = config.base_delay * (config.exponential_base ** attempt)

    # Cap at max delay
    delay = min(delay, config.max_delay)

    # Add jitter to prevent thundering herd
    if config.jitter:
        jitter_range = delay * config.jitter_factor
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
):
    """
    Decorator for retry with exponential backoff

    Args:
        config: Retry configuration (uses defaults if None)
        on_retry: Callback function(attempt, exception, delay) called before retry

    Usage:
        @retry_with_backoff(RetryConfig(max_attempts=3))
        def call_api():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = calculate_delay(attempt, config)

                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        if on_retry:
                            on_retry(attempt, e, delay)

                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed. "
                            f"Last error: {e}"
                        )

                except Exception as e:
                    # Non-retryable exception, raise immediately
                    logger.error(f"Non-retryable exception: {e}")
                    raise

            # All retries exhausted
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class RetryContext:
    """
    Context manager for retry logic with state tracking
    Useful for manual retry control
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
        self.total_delay = 0.0

    def should_retry(self, exception: Exception) -> bool:
        """Check if should retry after exception"""
        if not isinstance(exception, self.config.retryable_exceptions):
            return False

        self.last_exception = exception
        self.attempt += 1

        return self.attempt < self.config.max_attempts

    def wait(self):
        """Wait before next retry"""
        delay = calculate_delay(self.attempt - 1, self.config)
        self.total_delay += delay
        time.sleep(delay)
        return delay

    def get_stats(self) -> dict:
        """Get retry statistics"""
        return {
            'attempts': self.attempt,
            'max_attempts': self.config.max_attempts,
            'total_delay': self.total_delay,
            'last_exception': str(self.last_exception) if self.last_exception else None
        }


class CircuitBreaker:
    """
    Circuit breaker pattern for external services
    Prevents cascade failures by failing fast when service is unhealthy
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        name: str = "default"
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Failures before opening circuit
            success_threshold: Successes needed to close circuit
            timeout: Time in open state before testing
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name

        self._failures = 0
        self._successes = 0
        self._state = "closed"  # closed, open, half-open
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> str:
        """Get current circuit state"""
        if self._state == "open":
            if self._last_failure_time and time.time() - self._last_failure_time > self.timeout:
                self._state = "half-open"
                logger.info(f"Circuit breaker '{self.name}' transitioning to half-open")

        return self._state

    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        state = self.state

        if state == "closed":
            return True
        elif state == "half-open":
            return True  # Allow test requests
        else:  # open
            return False

    def record_success(self):
        """Record successful execution"""
        if self._state == "half-open":
            self._successes += 1
            if self._successes >= self.success_threshold:
                self._close()
        else:
            self._failures = 0

    def record_failure(self, exception: Exception):
        """Record failed execution"""
        self._failures += 1
        self._successes = 0
        self._last_failure_time = time.time()

        if self._state == "half-open":
            self._open()
        elif self._failures >= self.failure_threshold:
            self._open()

        logger.warning(
            f"Circuit breaker '{self.name}' recorded failure "
            f"({self._failures}/{self.failure_threshold}): {exception}"
        )

    def _open(self):
        """Open the circuit"""
        self._state = "open"
        logger.warning(f"Circuit breaker '{self.name}' OPENED")

    def _close(self):
        """Close the circuit"""
        self._state = "closed"
        self._failures = 0
        self._successes = 0
        logger.info(f"Circuit breaker '{self.name}' CLOSED")

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator usage"""
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not self.can_execute():
                raise TradingError(
                    f"Circuit breaker '{self.name}' is open",
                    error_code="CIRCUIT_OPEN",
                    recoverable=True
                )

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result

            except Exception as e:
                self.record_failure(e)
                raise

        return wrapper

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        return {
            'name': self.name,
            'state': self.state,
            'failures': self._failures,
            'failure_threshold': self.failure_threshold,
            'successes': self._successes,
            'success_threshold': self.success_threshold,
            'last_failure': self._last_failure_time
        }
