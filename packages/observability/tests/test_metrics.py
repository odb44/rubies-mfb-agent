from concurrent.futures import ThreadPoolExecutor

import pytest

from rubies_observability.metrics import MetricsRegistry


@pytest.fixture
def registry() -> MetricsRegistry:
    return MetricsRegistry()


def test_records_request_count_and_duration(
    registry: MetricsRegistry,
) -> None:
    registry.record(
        component="agent",
        operation="banking_tool_call",
        outcome="success",
        duration_ms=120.0,
    )

    snapshot = registry.snapshot()

    assert snapshot["requests"] == [
        {
            "component": "agent",
            "operation": "banking_tool_call",
            "outcome": "success",
            "count": 1,
        }
    ]

    duration = snapshot["durations"][0]

    assert duration["count"] == 1
    assert duration["total_ms"] == 120.0
    assert duration["average_ms"] == 120.0
    assert duration["max_ms"] == 120.0
    assert duration["buckets"]["le_250ms"] == 1
    assert duration["buckets"]["le_inf"] == 1


def test_aggregates_multiple_duration_observations(
    registry: MetricsRegistry,
) -> None:
    for duration in (50.0, 100.0, 250.0):
        registry.record(
            component="banking_api",
            operation="http_request",
            outcome="success",
            duration_ms=duration,
        )

    duration = registry.snapshot()["durations"][0]

    assert duration["count"] == 3
    assert duration["total_ms"] == 400.0
    assert round(duration["average_ms"], 2) == 133.33
    assert duration["max_ms"] == 250.0


def test_rejects_unbounded_component_labels(
    registry: MetricsRegistry,
) -> None:
    with pytest.raises(ValueError, match="component"):
        registry.record(
            component="customer-12345",
            operation="http_request",
            outcome="success",
        )


def test_rejects_unbounded_operation_labels(
    registry: MetricsRegistry,
) -> None:
    with pytest.raises(ValueError, match="operation"):
        registry.record(
            component="agent",
            operation="account-123456",
            outcome="success",
        )


@pytest.mark.parametrize(
    "duration",
    [-1.0, float("nan"), float("inf"), float("-inf"), True],
)
def test_rejects_invalid_durations(
    registry: MetricsRegistry,
    duration: float,
) -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        registry.record(
            component="agent",
            operation="banking_tool_call",
            outcome="success",
            duration_ms=duration,
        )


def test_concurrent_updates_are_thread_safe(
    registry: MetricsRegistry,
) -> None:
    def record_many(_: int) -> None:
        for _ in range(100):
            registry.record(
                component="mcp_server",
                operation="get_transaction_status",
                outcome="success",
                duration_ms=25.0,
            )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record_many, range(8)))

    snapshot = registry.snapshot()

    assert snapshot["requests"][0]["count"] == 800
    assert snapshot["durations"][0]["count"] == 800
    assert snapshot["durations"][0]["total_ms"] == 20_000.0


def test_reset_clears_metrics(
    registry: MetricsRegistry,
) -> None:
    registry.record(
        component="agent",
        operation="policy_retrieval",
        outcome="no_results",
        duration_ms=15.0,
    )

    registry.reset()

    assert registry.snapshot() == {
        "requests": [],
        "durations": [],
    }