
"""Thread-safe model usage and cost metrics for the observability dashboard."""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any


def _read_price(name: str) -> Decimal | None:
    """Read a non-negative USD price per million tokens."""
    raw_value = os.getenv(name, "").strip()

    if not raw_value:
        return None

    try:
        value = Decimal(raw_value)
    except InvalidOperation:
        return None

    if not value.is_finite() or value < 0:
        return None

    return value


def _read_field(entry: Any, name: str) -> Any:
    """Read a field from a TokenUsage object or dictionary."""
    if isinstance(entry, dict):
        return entry.get(name)

    return getattr(entry, name, None)


class ModelMetricsRegistry:
    """Aggregate model-call metrics and per-turn model costs."""

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

        # Pricing applies to the configured Bedrock model only.
        self._pricing_model = os.getenv("BEDROCK_MODEL_ID", "").strip()
        self._input_price = _read_price(
            "BEDROCK_INPUT_PRICE_PER_MILLION_USD"
        )
        self._output_price = _read_price(
            "BEDROCK_OUTPUT_PRICE_PER_MILLION_USD"
        )
        self._cache_read_price = _read_price(
            "BEDROCK_CACHE_READ_PRICE_PER_MILLION_USD"
        )
        self._cache_write_price = _read_price(
            "BEDROCK_CACHE_WRITE_PRICE_PER_MILLION_USD"
        )

        self._turns = 0
        self._costed_turns = 0
        self._total_cost_usd = Decimal("0")
        self._last_cost_per_turn_usd: Decimal | None = None
        self._cost_available = False

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

    def _calculate_turn_cost(
        self,
        usage: list[Any] | None,
    ) -> Decimal | None:
        """Calculate the cost of all model usage entries in one run."""
        if not usage:
            return None

        # Base input/output pricing is always required.
        # Cache pricing is required only when cached tokens are reported.
        if (
            not self._pricing_model
            or self._input_price is None
            or self._output_price is None
        ):
            return None

        total_cost = Decimal("0")
        million = Decimal("1000000")

        for entry in usage:
            model = _read_field(entry, "model")

            if model != self._pricing_model:
                return None

            input_tokens = _read_field(entry, "input_tokens")
            output_tokens = _read_field(entry, "output_tokens")

            if input_tokens is None or output_tokens is None:
                return None

            cached_tokens = _read_field(entry, "cached_input_tokens") or 0
            cache_write_tokens = (
                _read_field(entry, "cache_write_input_tokens") or 0
            )

            try:
                input_tokens = int(input_tokens)
                output_tokens = int(output_tokens)
                cached_tokens = int(cached_tokens)
                cache_write_tokens = int(cache_write_tokens)
            except (TypeError, ValueError):
                return None

            if min(
                input_tokens,
                output_tokens,
                cached_tokens,
                cache_write_tokens,
            ) < 0:
                return None

            if cached_tokens + cache_write_tokens > input_tokens:
                return None

            # Do not calculate an incomplete cost when cache pricing
            # is required but has not been configured.
            if cached_tokens > 0 and self._cache_read_price is None:
                return None

            if (
                cache_write_tokens > 0
                and self._cache_write_price is None
            ):
                return None

            regular_input_tokens = (
                input_tokens - cached_tokens - cache_write_tokens
            )

            entry_cost = (
                Decimal(regular_input_tokens) * self._input_price
                + Decimal(output_tokens) * self._output_price
            )

            if cached_tokens > 0:
                entry_cost += (
                    Decimal(cached_tokens) * self._cache_read_price
                )

            if cache_write_tokens > 0:
                entry_cost += (
                    Decimal(cache_write_tokens) * self._cache_write_price
                )

            entry_cost /= million
            total_cost += entry_cost

        return total_cost

    def record_turn(
        self,
        *,
        usage: list[Any] | None,
        run_id: str | None = None,
        thread_id: str | None = None,
    ) -> None:
        """Record cost once for the complete AG-UI run."""
        del run_id, thread_id  # Reserved for future per-run attribution.

        cost = self._calculate_turn_cost(usage)

        with self._lock:
            self._turns += 1
            self._last_cost_per_turn_usd = cost

            if cost is not None:
                self._cost_available = True
                self._costed_turns += 1
                self._total_cost_usd += cost

    def snapshot(self) -> dict[str, Any]:
        """Return a consistent snapshot for API responses."""
        with self._lock:
            pricing_configured = (
                bool(self._pricing_model)
                and self._input_price is not None
                and self._output_price is not None
                and (
                    self._cache_read_input_tokens == 0
                    or self._cache_read_price is not None
                )
                and (
                    self._cache_write_input_tokens == 0
                    or self._cache_write_price is not None
                )
            )

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
                "turns": self._turns,
                "costedTurns": self._costed_turns,
                "costAvailable": self._cost_available,
                "pricingConfigured": pricing_configured,
                "pricingModel": self._pricing_model or None,
                "totalModelCostUsd": (
                    round(float(self._total_cost_usd), 8)
                    if self._costed_turns
                    else None
                ),
                "lastCostPerTurnUsd": (
                    round(float(self._last_cost_per_turn_usd), 8)
                    if self._last_cost_per_turn_usd is not None
                    else None
                ),
                "averageCostPerTurnUsd": (
                    round(
                        float(self._total_cost_usd / self._costed_turns),
                        8,
                    )
                    if self._costed_turns
                    else None
                ),
            }


model_metrics = ModelMetricsRegistry()