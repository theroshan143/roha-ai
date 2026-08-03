import time
import threading
import os


class CircuitBreaker:
    """Simple in-memory circuit breaker.

    Usage:
      cb = CircuitBreaker(fail_threshold=3, cooldown=300)
      if not cb.call_allowed():
          # skip calling remote model
      try:
          result = call_remote()
          cb.record_success()
      except Exception:
          cb.record_failure()
          raise
    """

    def __init__(self, fail_threshold: int = None, cooldown: int = None):
        self.fail_threshold = int(fail_threshold or int(os.environ.get("MODEL_CB_THRESHOLD", "3")))
        self.cooldown = int(cooldown or int(os.environ.get("MODEL_CB_COOLDOWN", "300")))
        self._lock = threading.Lock()
        self._fail_count = 0
        self._tripped_at = None

    def call_allowed(self) -> bool:
        with self._lock:
            if self._tripped_at is None:
                return True
            # if cooling period has passed, reset
            if time.time() - self._tripped_at >= self.cooldown:
                self._fail_count = 0
                self._tripped_at = None
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._fail_count = 0
            self._tripped_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._fail_count += 1
            if self._fail_count >= self.fail_threshold:
                self._tripped_at = time.time()

    def time_until_reset(self) -> int:
        with self._lock:
            if self._tripped_at is None:
                return 0
            remaining = int(self.cooldown - (time.time() - self._tripped_at))
            return max(0, remaining)
