from datetime import UTC, datetime, timedelta

import pytest
from rubies_shared import (
    AuditEvent,
    ConfirmationRequest,
    ConfirmationStatus,
    CustomerIdentity,
    ResultStatus,
    ToolResult,
)


def test_customer_identity_requires_non_empty_ids() -> None:
    identity = CustomerIdentity(
        customer_id="CUS-0001",
        session_id="SESSION-001",
        verified=True,
    )

    assert identity.customer_id == "CUS-0001"
    assert identity.verified is True

    with pytest.raises(ValueError):
        CustomerIdentity(
            customer_id=" ",
            session_id="SESSION-001",
            verified=True,
        )


def test_successful_tool_result() -> None:
    result = ToolResult(
        status=ResultStatus.SUCCESS,
        message="Balance retrieved.",
        data={"currency": "NGN"},
    )

    assert result.status == ResultStatus.SUCCESS
    assert result.data["currency"] == "NGN"


def test_successful_result_cannot_have_error_code() -> None:
    with pytest.raises(ValueError):
        ToolResult(
            status=ResultStatus.SUCCESS,
            message="Completed.",
            error_code="UNEXPECTED_ERROR",
        )


def test_unknown_outcome_requires_operation_id() -> None:
    with pytest.raises(ValueError):
        ToolResult(
            status=ResultStatus.UNKNOWN,
            message="The outcome could not be determined.",
        )

    result = ToolResult(
        status=ResultStatus.UNKNOWN,
        message="Reconciliation required.",
        operation_id="OP-0001",
    )

    assert result.operation_id == "OP-0001"


def test_confirmation_requires_valid_timezone_aware_dates() -> None:
    now = datetime.now(UTC)

    request = ConfirmationRequest(
        confirmation_id="CONF-001",
        customer_id="CUS-0001",
        action="block_card",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    assert request.status == ConfirmationStatus.PENDING

    with pytest.raises(ValueError):
        ConfirmationRequest(
            confirmation_id="CONF-002",
            customer_id="CUS-0001",
            action="block_card",
            created_at=now,
            expires_at=now,
        )


def test_confirmation_rejects_naive_datetime() -> None:
    now = datetime.now()

    with pytest.raises(ValueError):
        ConfirmationRequest(
            confirmation_id="CONF-003",
            customer_id="CUS-0001",
            action="block_card",
            created_at=now,
            expires_at=now + timedelta(minutes=5),
        )


def test_audit_event_requires_timezone_aware_timestamp() -> None:
    event = AuditEvent(
        event_id="AUD-001",
        occurred_at=datetime.now(UTC),
        actor_id="CUS-0001",
        action="get_balance",
        outcome="SUCCESS",
        correlation_id="REQ-001",
    )

    assert event.action == "get_balance"

    with pytest.raises(ValueError):
        AuditEvent(
            event_id="AUD-002",
            occurred_at=datetime.now(),
            actor_id="CUS-0001",
            action="get_balance",
            outcome="SUCCESS",
            correlation_id="REQ-002",
        )