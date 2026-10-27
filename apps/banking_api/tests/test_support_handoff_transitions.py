"""Tests for support handoff acknowledgement and failure transitions."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from rubies_banking_api.models.support_handoff import HandoffStatus
from rubies_banking_api.services.support_handoff_service import (
    SupportHandoffService,
)


@pytest.fixture
def setup_handoff_service():
    """Create a service with a mocked database and pending handoff."""
    db = MagicMock()
    service = SupportHandoffService(db)

    handoff = SimpleNamespace(
        reference="HND-TEST001",
        status=HandoffStatus.PENDING_ACKNOWLEDGEMENT.value,
        acknowledgement_reference=None,
        acknowledged_at=None,
        failure_reason=None,
    )

    (
        db.query.return_value
        .filter.return_value
        .with_for_update.return_value
        .one_or_none.return_value
    ) = handoff

    return service, db, handoff


def test_pending_handoff_can_be_acknowledged(setup_handoff_service):
    service, db, handoff = setup_handoff_service

    result = service.acknowledge(
        reference="HND-TEST001",
        acknowledgement_reference="SUPPORT-CASE-123",
    )

    assert result.status == HandoffStatus.ACKNOWLEDGED.value
    assert result.acknowledgement_reference == "SUPPORT-CASE-123"
    assert result.acknowledged_at is not None
    db.flush.assert_called_once()


def test_pending_handoff_can_be_marked_failed(setup_handoff_service):
    service, db, handoff = setup_handoff_service

    result = service.mark_failed(
        reference="HND-TEST001",
        failure_reason="Support destination unavailable.",
    )

    assert result.status == HandoffStatus.FAILED.value
    assert result.failure_reason == "Support destination unavailable."
    db.flush.assert_called_once()


def test_acknowledged_handoff_cannot_be_acknowledged_again(
    setup_handoff_service,
):
    service, db, handoff = setup_handoff_service
    handoff.status = HandoffStatus.ACKNOWLEDGED.value

    with pytest.raises(ValueError, match="Only pending handoffs"):
        service.acknowledge(
            reference="HND-TEST001",
            acknowledgement_reference="SUPPORT-CASE-456",
        )

    db.flush.assert_not_called()


def test_acknowledged_handoff_cannot_be_marked_failed(
    setup_handoff_service,
):
    service, db, handoff = setup_handoff_service
    handoff.status = HandoffStatus.ACKNOWLEDGED.value

    with pytest.raises(ValueError, match="Only pending handoffs"):
        service.mark_failed(
            reference="HND-TEST001",
            failure_reason="Attempted invalid transition.",
        )

    db.flush.assert_not_called()


def test_acknowledgement_requires_reference(setup_handoff_service):
    service, db, _ = setup_handoff_service

    with pytest.raises(
        ValueError,
        match="An acknowledgement reference is required",
    ):
        service.acknowledge(
            reference="HND-TEST001",
            acknowledgement_reference="   ",
        )

    db.query.assert_not_called()


def test_failure_requires_reason(setup_handoff_service):
    service, db, _ = setup_handoff_service

    with pytest.raises(
        ValueError,
        match="A failure reason is required",
    ):
        service.mark_failed(
            reference="HND-TEST001",
            failure_reason="   ",
        )

    db.query.assert_not_called()


def test_transition_rejects_unknown_handoff(setup_handoff_service):
    service, db, _ = setup_handoff_service

    (
        db.query.return_value
        .filter.return_value
        .with_for_update.return_value
        .one_or_none.return_value
    ) = None

    with pytest.raises(ValueError, match="Support handoff not found"):
        service.acknowledge(
            reference="HND-DOES-NOT-EXIST",
            acknowledgement_reference="SUPPORT-CASE-789",
        )

    db.flush.assert_not_called()