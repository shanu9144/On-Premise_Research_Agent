import random
import time


class FallbackManager:
    """Per-process retry policy and circuit breaker."""

    def __init__(self, max_retries=1, failure_threshold=3, cooldown_seconds=60):
        self.max_retries = max(0, min(max_retries, 2))
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = {}
        self.open_until = {}

    def available(self, name):
        return self.open_until.get(name, 0) <= time.monotonic()

    def record_success(self, name):
        self.failures[name] = 0

    def record_failure(self, name):
        self.failures[name] = self.failures.get(name, 0) + 1
        if self.failures[name] >= self.failure_threshold:
            self.open_until[name] = time.monotonic() + self.cooldown_seconds

    def should_retry(self, error, attempt, operation):
        # Crawls are never retried: a timed-out job may still be running remotely.
        return error.retryable and attempt < self.max_retries and operation != "crawl"

    def backoff(self, attempt):
        time.sleep(min(2, 0.25 * 2 ** attempt + random.uniform(0, 0.1)))
