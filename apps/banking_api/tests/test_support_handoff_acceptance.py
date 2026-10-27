"""Acceptance tests for the customer support handoff workflow."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from rubies_banking_api.models.support_handoff import (
    HandoffPriority,
    HandoffRoute,
    HandoffStatus,
    SupportHandoff,
)
from rubies_banking_api.services.support_handoff_service import (
    SupportHandoffService,
)


@pytest.fixture
def identity():
    """Represent a verified customer identity."""
    return SimpleNamespace(
        customer_id="CUST-001",
        session_id="SESSION-001",
        verified=True,
    )


@pytest.fixture
def setup_service(identity):
    """Build the service with mocked database repositories."""
    db = MagicMock()
    service = SupportHandoffService(db)

    # The service creates real repository instances, so replace them with mocks.
    service.customers = MagicMock()
    service.handoffs = MagicMock()

    customer = SimpleNamespace(
        id=1,
        is_active=True,
    )
    service.customers.get_by_reference.return_value = customer

    handoff = SimpleNamespace(
        id=1,
        reference="HND-TEST001",
        customer_id=1,
        status=HandoffStatus.PENDING_ACKNOWLEDGEMENT.value,
        reason="Unresolved payment",
        summary="The customer reports an unreflected payment.",
        route=HandoffRoute.PAYMENTS_OPERATIONS.value,
        priority=HandoffPriority.P2.value,
        actions_attempted=["transaction status enquiry"],
        unresolved_questions=["Where is the payment?"],
        correlation_id="acceptance-test-001",
        acknowledgement_reference=None,
        acknowledged_at=None,
        failure_reason=None,
    )

    service.handoffs.add.return_value = handoff
    service.handoffs.get_by_reference.return_value = handoff

    # Acknowledge/fail operations query the database directly and lock the row.
    (
        db.query.return_value
        .filter.return_value
        .with_for_update.return_value
        .one_or_none.return_value
    ) = handoff

    return service, db, customer, handoff

def test_create_persists_pending_handoff(setup_service, identity):
    """Creation records a handoff with a reference and pending status."""
    service, _, customer, handoff = setup_service

    result = service.create(
        identity=identity,
        reason="Unresolved payment",
        summary="The customer reports an unreflected payment.",
        route=HandoffRoute.PAYMENTS_OPERATIONS.value,
        priority=HandoffPriority.P2.value,
        actions_attempted=["transaction status enquiry"],
        unresolved_questions=["Where is the payment?"],
        correlation_id="acceptance-test-001",
    )

    service.handoffs.add.assert_called_once()
    created_record = service.handoffs.add.call_args.args[0]

    assert isinstance(created_record, SupportHandoff)
    assert created_record.customer_id == customer.id
    assert created_record.status == (
        HandoffStatus.PENDING_ACKNOWLEDGEMENT.value
    )
    assert result.reference == "HND-TEST001"


def test_acknowledgement_records_reference_and_timestamp(
    setup_service,
):
    """A pending handoff records explicit acknowledgement."""
    service, db, _, handoff = setup_service

    before = datetime.now(UTC)

    result = service.acknowledge(
        reference="HND-TEST001",
        acknowledgement_reference="SUPPORT-CASE-123",
    )

    after = datetime.now(UTC)

    assert result.status == HandoffStatus.ACKNOWLEDGED.value
    assert result.acknowledgement_reference == "SUPPORT-CASE-123"
    assert before <= result.acknowledged_at <= after
    db.flush.assert_called_once()


def test_failure_records_reason(setup_service):
    """A pending handoff can be marked failed with a reason."""
    service, db, _, handoff = setup_service

    result = service.mark_failed(
        reference="HND-TEST001",
        failure_reason="Support destination unavailable.",
    )

    assert result.status == HandoffStatus.FAILED.value
    assert result.failure_reason == "Support destination unavailable."
    db.flush.assert_called_once()


@pytest.mark.parametrize(
    ("initial_status", "operation"),
    [
        (
            HandoffStatus.ACKNOWLEDGED.value,
            "acknowledge",
        ),
        (
            HandoffStatus.ACKNOWLEDGED.value,
            "mark_failed",
        ),
        (
            HandoffStatus.FAILED.value,
            "acknowledge",
        ),
        (
            HandoffStatus.FAILED.value,
            "mark_failed",
        ),
    ],
)
def test_terminal_handoff_cannot_transition_again(
    setup_service,
    initial_status,
    operation,
):
    """Acknowledged and failed handoffs cannot transition again."""
    service, db, _, handoff = setup_service
    handoff.status = initial_status

    with pytest.raises(ValueError, match="Only pending handoffs"):
        if operation == "acknowledge":
            service.acknowledge(
                reference="HND-TEST001",
                acknowledgement_reference="SUPPORT-CASE-456",
            )
        else:
            service.mark_failed(
                reference="HND-TEST001",
                failure_reason="Attempted invalid transition.",
            )

    db.flush.assert_not_called()


def test_customer_cannot_retrieve_another_customers_handoff(
    setup_service,
    identity,
):
    """Customer retrieval is scoped to the active customer's database ID."""
    service, _, customer, _ = setup_service

    service.get_for_customer(
        identity=identity,
        reference="HND-OTHER-CUSTOMER",
    )

    service.handoffs.get_by_reference.assert_called_once_with(
        reference="HND-OTHER-CUSTOMER",
        customer_id=customer.id,
    )