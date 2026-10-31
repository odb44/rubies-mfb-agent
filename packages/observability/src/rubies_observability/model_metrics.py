"""Thread-safe model usage metrics for the observability dashboard."""

from __future__ import annotations

from threading import Lock
from typing import Any


class ModelMetricsRegistry:
    """Aggregate provider-reported usage across model calls."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._model_calls = 0
        self._successful_calls = 0
        self._failed_calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._total_tokens = 0
        self._cache_read_input_tokens = 0
        self._cache_write_input_tokens = 0
        self._latency_total_ms = 0.0
        self._latency_max_ms = 0.0
        self._latency_count = 0
        self._ttfb_total_ms = 0.0
        self._ttfb_count = 0
        self._usage_available = False

    def record_call(
        self,
        *,
        usage: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        ttfb_ms: float | None = None,
        success: bool = True,
    ) -> None:
        """Record one model call and its reported metrics."""
        usage = usage or {}

        with self._lock:
            self._model_calls += 1

            if success:
                self._successful_calls += 1
            else:
                self._failed_calls += 1

            input_tokens = int(usage.get("inputTokens", 0) or 0)
            output_tokens = int(usage.get("outputTokens", 0) or 0)
            total_tokens = int(
                usage.get("totalTokens", input_tokens + output_tokens) or 0
            )

            if usage:
                self._usage_available = True

            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._total_tokens += total_tokens
            self._cache_read_input_tokens += int(
                usage.get("cacheReadInputTokens", 0) or 0
            )
            self._cache_write_input_tokens += int(
                usage.get("cacheWriteInputTokens", 0) or 0
            )

            if latency_ms is not None:
                self._latency_total_ms += latency_ms
                self._latency_max_ms = max(
                    self._latency_max_ms,
                    latency_ms,
                )
                self._latency_count += 1

            if ttfb_ms is not None:
                self._ttfb_total_ms += ttfb_ms
                self._ttfb_count += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a consistent snapshot for API responses."""
        with self._lock:
            return {
                "available": self._usage_available,
                "modelCalls": self._model_calls,
                "successfulCalls": self._successful_calls,
                "failedCalls": self._failed_calls,
                "inputTokens": self._input_tokens,
                "outputTokens": self._output_tokens,
                "totalTokens": self._total_tokens,
                "cacheReadInputTokens": self._cache_read_input_tokens,
                "cacheWriteInputTokens": self._cache_write_input_tokens,
                "averageLatencyMs": (
                    round(
                        self._latency_total_ms / self._latency_count,
                        2,
                    )
                    if self._latency_count
                    else None
                ),
                "maxLatencyMs": (
                    round(self._latency_max_ms, 2)
                    if self._latency_count
                    else None
                ),
                "averageTtfbMs": (
                    round(self._ttfb_total_ms / self._ttfb_count, 2)
                    if self._ttfb_count
                    else None
                ),
            }


model_metrics = ModelMetricsRegistry()