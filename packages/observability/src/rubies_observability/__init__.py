"""Shared observability utilities for Rubies MFB."""

from rubies_observability.metrics import (
    MetricsRegistry,
    get_metrics_snapshot,
    metrics,
    record_metric,
)
from rubies_observability.structured_logging import (
    JsonFormatter,
    configure_logging,
    correlation_context,
    get_correlation_id,
    log_event,
    set_correlation_id,
    timed_operation,
)

__all__ = [
    "JsonFormatter",
    "MetricsRegistry",
    "configure_logging",
    "correlation_context",
    "get_correlation_id",
    "get_metrics_snapshot",
    "log_event",
    "metrics",
    "record_metric",
    "set_correlation_id",
    "timed_operation",
]