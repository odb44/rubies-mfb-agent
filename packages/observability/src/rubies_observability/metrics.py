"""Thread-safe application metrics with bounded label values."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import isfinite
from threading import Lock
from typing import Any

ALLOWED_COMPONENTS = frozenset({
    "agent",
    "banking_api",
})

ALLOWED_OUTCOMES = frozenset({
    "success",
    "failure",
    "error",
    "timeout",
    "no_results",
    "rejected",
})

ALLOWED_OPERATIONS = frozenset({
    "http_request",
    "banking_tool_call",
    "policy_retrieval",
    "verify_customer",
    "get_balance",
    "get_mini_statement",
    "get_transaction_status",
    "open_dispute",
    "block_card",
    "check_loan_eligibility",
    "get_loan_status",
    "handoff_to_human",
    "support_handoff",
    "unknown",
})

# Fixed duration buckets in milliseconds.
DURATION_BUCKETS_MS = (
    10.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
    5000.0,
)


@dataclass
class _DurationSummary:
    """Aggregated duration statistics without retaining individual samples."""

    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    buckets: Counter[str] = field(default_factory=Counter)

    def observe(self, duration_ms: float) -> None:
        self.count += 1
        self.total_ms += duration_ms
        self.max_ms = max(self.max_ms, duration_ms)

        for boundary in DURATION_BUCKETS_MS:
            if duration_ms <= boundary:
                self.buckets[f"le_{int(boundary)}ms"] += 1

        self.buckets["le_inf"] += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 3),
            "average_ms": round(
                self.total_ms / self.count,
                3,
            ) if self.count else 0.0,
            "max_ms": round(self.max_ms, 3),
            "buckets": dict(self.buckets),
        }


class MetricsRegistry:
    """Collect bounded-label counters and duration summaries."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._request_counts: Counter[tuple[str, str, str]] = Counter()
        self._durations: dict[
            tuple[str, str],
            _DurationSummary,
        ] = {}

    @staticmethod
    def _validate_labels(
        component: str,
        operation: str,
        outcome: str,
    ) -> None:
        if component not in ALLOWED_COMPONENTS:
            raise ValueError(
                f"Unsupported metrics component: {component!r}"
            )

        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(
                f"Unsupported metrics operation: {operation!r}"
            )

        if outcome not in ALLOWED_OUTCOMES:
            raise ValueError(
                f"Unsupported metrics outcome: {outcome!r}"
            )

    def record(
        self,
        *,
        component: str,
        operation: str,
        outcome: str,
        duration_ms: float | None = None,
    ) -> None:
        """Record one operation and optionally its duration."""

        self._validate_labels(component, operation, outcome)

        if duration_ms is not None:
            if (
                isinstance(duration_ms, bool)
                or not isinstance(duration_ms, (int, float))
                or not isfinite(duration_ms)
                or duration_ms < 0
            ):
                raise ValueError(
                    "duration_ms must be a finite, non-negative number"
                )

        counter_key = (component, operation, outcome)
        duration_key = (component, operation)

        with self._lock:
            self._request_counts[counter_key] += 1

            if duration_ms is not None:
                summary = self._durations.setdefault(
                    duration_key,
                    _DurationSummary(),
                )
                summary.observe(float(duration_ms))

    def snapshot(self) -> dict[str, Any]:
        """Return a consistent, JSON-serializable metrics snapshot."""

        with self._lock:
            requests = [
                {
                    "component": component,
                    "operation": operation,
                    "outcome": outcome,
                    "count": count,
                }
                for (component, operation, outcome), count
                in sorted(self._request_counts.items())
            ]

            durations = [
                {
                    "component": component,
                    "operation": operation,
                    **summary.snapshot(),
                }
                for (component, operation), summary
                in sorted(self._durations.items())
            ]

        return {
            "requests": requests,
            "durations": durations,
        }

    def reset(self) -> None:
        """Clear all metrics. Intended for tests and controlled resets."""

        with self._lock:
            self._request_counts.clear()
            self._durations.clear()


# One shared registry per application process.
metrics = MetricsRegistry()


def record_metric(
    *,
    component: str,
    operation: str,
    outcome: str,
    duration_ms: float | None = None,
) -> None:
    """Record an event in the shared application registry."""

    metrics.record(
        component=component,
        operation=operation,
        outcome=outcome,
        duration_ms=duration_ms,
    )


def get_metrics_snapshot() -> dict[str, Any]:
    """Return the current metrics snapshot."""

    return metrics.snapshot()
