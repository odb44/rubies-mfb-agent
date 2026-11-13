"""Structured, privacy-conscious logging utilities for Rubies MFB."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "rubies_correlation_id",
    default=None,
)

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "credential",
    "pin",
    "cvv",
    "card_number",
    "account_number",
    "account_no",
    "customer_id",
    "transaction_reference",
    "access_key",
)

MAX_STRING_LENGTH = 500


def _is_sensitive_key(key: str) -> bool:
    """Determine whether a metadata key may contain sensitive information."""
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def _sanitize(value: Any, *, key: str = "") -> Any:
    """Redact sensitive metadata and limit the size of logged values."""
    if key and _is_sensitive_key(key):
        return "[REDACTED]"

    if isinstance(value, Mapping):
        return {
            str(item_key): _sanitize(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]

    if isinstance(value, str):
        return value[:MAX_STRING_LENGTH]

    if value is None or isinstance(value, (bool, int, float)):
        return value

    return str(value)[:MAX_STRING_LENGTH]


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set the current context's correlation ID and return it."""
    value = correlation_id or uuid.uuid4().hex
    correlation_id_var.set(value)
    return value


def get_correlation_id() -> str | None:
    """Return the current context's correlation ID."""
    return correlation_id_var.get()


@contextmanager
def correlation_context(
    correlation_id: str | None = None,
) -> Iterator[str]:
    """Temporarily establish a correlation ID and restore the previous one."""
    value = correlation_id or uuid.uuid4().hex
    context_token = correlation_id_var.set(value)

    try:
        yield value
    finally:
        correlation_id_var.reset(context_token)


class JsonFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "severity": record.levelname,
            "component": getattr(record, "component", record.name),
            "event": getattr(record, "event", record.getMessage()),
            "correlation_id": (
                getattr(record, "correlation_id", None)
                or get_correlation_id()
            ),
        }

        metadata = getattr(record, "metadata", {})
        if isinstance(metadata, Mapping):
            payload["metadata"] = _sanitize(metadata)

        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms

        outcome = getattr(record, "outcome", None)
        if outcome is not None:
            payload["outcome"] = outcome

        # Expose the exception class without logging its potentially sensitive
        # message or traceback.
        exception_type = getattr(record, "exception_type", None)
        if exception_type is not None:
            payload["exception_type"] = exception_type

        # Support ordinary Python logging calls that include exc_info.
        if record.exc_info and "exception_type" not in payload:
            exception_class = record.exc_info[0]
            payload["exception_type"] = (
                exception_class.__name__
                if exception_class is not None
                else "Exception"
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )



def configure_logging(
    *,
    level: str = "INFO",
    logger_name: str = "rubies",
) -> logging.Logger:
    """Configure a UTF-8 JSON logger without duplicate handlers."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(level.upper())
    logger.propagate = False

    if not any(
        getattr(handler, "_rubies_json_handler", False)
        for handler in logger.handlers
    ):
        stream = sys.stderr

        # Preserve the original stream while enabling UTF-8 output
        # where the runtime supports reconfiguration.
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(
                    encoding="utf-8",
                    errors="backslashreplace",
                )
            except (OSError, ValueError):
                pass

        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        handler._rubies_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)

    return logger


def log_event(
    logger: logging.Logger,
    *,
    component: str,
    event: str,
    outcome: str,
    level: int = logging.INFO,
    metadata: Mapping[str, Any] | None = None,
    duration_ms: float | None = None,
    exception_type: str | None = None,
) -> None:
    """Write a structured event with sanitized metadata."""
    extra: dict[str, Any] = {
        "component": component,
        "event": event,
        "outcome": outcome,
        "metadata": _sanitize(metadata or {}),
    }

    correlation_id = get_correlation_id()
    if correlation_id:
        extra["correlation_id"] = correlation_id

    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)

    if exception_type is not None:
        extra["exception_type"] = exception_type

    logger.log(
        level,
        event,
        extra=extra,
    )


@contextmanager
def timed_operation(
    logger: logging.Logger,
    *,
    component: str,
    operation: str,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    """Log operation completion or failure with elapsed time."""
    start = time.perf_counter()

    try:
        yield

    except Exception as exc:
        log_event(
            logger,
            component=component,
            event=f"{operation}.failed",
            outcome="error",
            level=logging.ERROR,
            metadata=metadata,
            duration_ms=(time.perf_counter() - start) * 1000,
            exception_type=type(exc).__name__,
        )
        raise

    else:
        log_event(
            logger,
            component=component,
            event=f"{operation}.completed",
            outcome="success",
            metadata=metadata,
            duration_ms=(time.perf_counter() - start) * 1000,
        )
