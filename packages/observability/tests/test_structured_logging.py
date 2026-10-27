"""Tests for shared structured logging utilities."""

import json
import logging

import pytest

from rubies_observability import (
    JsonFormatter,
    configure_logging,
    correlation_context,
    get_correlation_id,
    log_event,
    timed_operation,
)


def test_logs_structured_json_with_correlation_id():
    logger = logging.getLogger("test.structured")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = CaptureHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    with correlation_context("corr-test-001"):
        log_event(
            logger,
            component="mcp_server",
            event="tool.invoked",
            outcome="success",
            metadata={"tool_name": "transaction_status"},
            duration_ms=12.5,
        )

    payload = json.loads(records[0])

    assert payload["component"] == "mcp_server"
    assert payload["event"] == "tool.invoked"
    assert payload["outcome"] == "success"
    assert payload["correlation_id"] == "corr-test-001"
    assert payload["duration_ms"] == 12.5
    assert payload["metadata"]["tool_name"] == "transaction_status"


def test_sensitive_metadata_is_redacted():
    logger = logging.getLogger("test.redaction")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = CaptureHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    log_event(
        logger,
        component="banking_api",
        event="request.completed",
        outcome="success",
        metadata={
            "customer_id": "CUSTOMER-123",
            "access_token": "secret-token",
            "tool_name": "transaction_status",
            "result": "found",
        },
    )

    payload = json.loads(records[0])

    assert payload["metadata"]["customer_id"] == "[REDACTED]"
    assert payload["metadata"]["access_token"] == "[REDACTED]"
    assert payload["metadata"]["tool_name"] == "transaction_status"
    assert payload["metadata"]["result"] == "found"
    assert "CUSTOMER-123" not in records[0]
    assert "secret-token" not in records[0]


def test_correlation_context_restores_previous_value():
    with correlation_context("outer"):
        assert get_correlation_id() == "outer"

        with correlation_context("inner"):
            assert get_correlation_id() == "inner"

        assert get_correlation_id() == "outer"

    assert get_correlation_id() is None


def test_timed_operation_logs_success():
    logger = logging.getLogger("test.timing")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = CaptureHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    with timed_operation(
        logger,
        component="agent",
        operation="retrieval",
        metadata={"knowledge_version": "v1"},
    ):
        pass

    payload = json.loads(records[0])

    assert payload["event"] == "retrieval.completed"
    assert payload["outcome"] == "success"
    assert payload["duration_ms"] >= 0


def test_timed_operation_logs_failure_and_reraises():
    logger = logging.getLogger("test.timing.failure")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = CaptureHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    with pytest.raises(RuntimeError, match="operation failed"):
        with timed_operation(
            logger,
            component="mcp_server",
            operation="banking_tool",
        ):
            raise RuntimeError("operation failed")

    payload = json.loads(records[0])

    assert payload["event"] == "banking_tool.failed"
    assert payload["outcome"] == "error"
    assert payload["exception_type"] == "RuntimeError"
    assert "operation failed" not in records[0]


def test_configure_logging_does_not_add_duplicate_handlers():
    logger = configure_logging(logger_name="test.configure")
    initial_count = len(logger.handlers)

    configure_logging(logger_name="test.configure")

    assert len(logger.handlers) == initial_count