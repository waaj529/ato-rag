"""Resilience: circuit breakers, bounded retries with jitter and graceful degradation."""

from enum import Enum
import random
import time
from threading import Lock
from typing import Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when call is rejected because circuit breaker is OPEN."""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.monotonic()
        self._lock = Lock()
        self._probe_in_flight = False

    def call(self, func: Callable[[], T]) -> T:
        with self._lock:
            now = time.monotonic()
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change <= self.recovery_timeout:
                    raise CircuitBreakerOpenError("Provider circuit is open")
                self.state = CircuitState.HALF_OPEN
            if self.state == CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    raise CircuitBreakerOpenError("Provider recovery probe is in progress")
                self._probe_in_flight = True
        try:
            result = func()
        except Exception:
            with self._lock:
                self.failure_count += 1
                self._probe_in_flight = False
                if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.last_state_change = time.monotonic()
            raise
        with self._lock:
            if self.state != CircuitState.OPEN:
                self.failure_count = 0
                self.state = CircuitState.CLOSED
            self._probe_in_flight = False
        return result


def bounded_retry(
    func: Callable[[], T],
    max_retries: int = 3,
    initial_backoff: float = 0.5,
    max_backoff: float = 10.0,
    jitter: bool = True,
) -> T:
    """Execute func with bounded retries, exponential backoff, and full jitter."""
    backoff = initial_backoff
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception:
            if attempt == max_retries:
                raise
            sleep_time = random.uniform(0, backoff) if jitter else backoff
            time.sleep(sleep_time)
            backoff = min(backoff * 2.0, max_backoff)
    raise RuntimeError("Retry loop exhausted")
