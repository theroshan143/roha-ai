import time
from app.circuit_breaker import CircuitBreaker


def test_circuit_breaker_trips_and_recovers():
    cb = CircuitBreaker(fail_threshold=2, cooldown=1)
    assert cb.call_allowed()
    cb.record_failure()
    assert cb.call_allowed()
    cb.record_failure()
    assert not cb.call_allowed()
    # wait for cooldown
    time.sleep(1.2)
    assert cb.call_allowed()