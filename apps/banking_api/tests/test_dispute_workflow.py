
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.models.dispute import Dispute
from rubies_banking_api.services.confirmation_payload import (
    hash_confirmation_payload,
)
from rubies_banking_api.services.dispute_service import DisputeService
from rubies_security.confirmations import ConfirmationRequiredError
from rubies_security.identity import CustomerMismatchError
from rubies_shared.identity import CustomerIdentity


@pytest.fixture
def identity() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="CUS-0007",
        session_id="session-001",
        verified=True,
    )


@pytest.fixture
def customer() -> Customer:
    return Customer(
        id=7,
        customer_reference="CUS-0007",
        full_name="Demo Customer",
        is_active=True,
    )


@pytest.fixture
def repositories() -> tuple[Mock, Mock, Mock, Mock]:
    dispute_repository = Mock()
    customer_repository = Mock()
    confirmation_repository = Mock()
    audit_repository = Mock()

    dispute_repository.add.side_effect = lambda dispute: dispute

    return (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    )


@pytest.fixture
def service(repositories: tuple[Mock, Mock, Mock, Mock]) -> DisputeService:
    (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    ) = repositories

    return DisputeService(
        dispute_repository=dispute_repository,
        customer_repository=customer_repository,
        confirmation_repository=confirmation_repository,
        audit_repository=audit_repository,
    )


@pytest.fixture
def approved_request() -> dict:
    return {
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reports a duplicate debit.",
    }


@pytest.fixture
def current_time() -> datetime:
    return datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def test_successful_dispute_workflow(
    service: DisputeService,
    repositories: tuple[Mock, Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    approved_request: dict,
    current_time: datetime,
) -> None:
    (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    ) = repositories

    customer_repository.get_by_reference.return_value = customer

    dispute = service.create_dispute(
        identity,
        confirmation_id="CONF-approved",
        category=approved_request["category"],
        description=approved_request["description"],
        correlation_id="CORR-001",
        now=current_time,
    )

    assert isinstance(dispute, Dispute)
    assert dispute.case_reference.startswith("DIS-")
    assert dispute.customer_id == customer.id
    assert dispute.transaction_id is None
    assert dispute.category == "DUPLICATE_DEBIT"
    assert dispute.status == "OPEN"

    confirmation_payload = {
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reports a duplicate debit.",
    }

    confirmation_repository.consume.assert_called_once_with(
        confirmation_id="CONF-approved",
        identity=identity,
        action="OPEN_DISPUTE",
        payload_hash=hash_confirmation_payload(confirmation_payload),
        now=current_time,
    )

    dispute_repository.add.assert_called_once_with(dispute)
    dispute_repository.db.flush.assert_called_once()
    audit_repository.record.assert_called_once()

    audit_event = audit_repository.record.call_args.args[0]
    assert audit_event.action == "OPEN_DISPUTE"
    assert audit_event.outcome == "SUCCESS"
    assert audit_event.correlation_id == "CORR-001"
    assert audit_event.details["category"] == "DUPLICATE_DEBIT"


def test_successful_dispute_workflow_with_transaction_reference(
    service: DisputeService,
    repositories: tuple[Mock, Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    approved_request: dict,
    current_time: datetime,
) -> None:
    (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    ) = repositories

    customer_repository.get_by_reference.return_value = customer

    transaction = Mock()
    transaction.id = 123
    transaction.reference = "DEMO-DUP-B-002"
    transaction.account.customer_id = customer.id

    dispute = service.create_dispute(
        identity,
        confirmation_id="CONF-transaction",
        category=approved_request["category"],
        description=approved_request["description"],
        correlation_id="CORR-006",
        transaction=transaction,
        now=current_time,
    )

    assert isinstance(dispute, Dispute)
    assert dispute.transaction_id == 123
    assert dispute.customer_id == customer.id

    confirmation_payload = {
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reports a duplicate debit.",
        "transaction_reference": "DEMO-DUP-B-002",
    }

    confirmation_repository.consume.assert_called_once_with(
        confirmation_id="CONF-transaction",
        identity=identity,
        action="OPEN_DISPUTE",
        payload_hash=hash_confirmation_payload(confirmation_payload),
        now=current_time,
    )

    dispute_repository.add.assert_called_once_with(dispute)
    dispute_repository.db.flush.assert_called_once()
    audit_repository.record.assert_called_once()


def test_missing_approval_prevents_dispute_creation(
    service: DisputeService,
    repositories: tuple[Mock, Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    approved_request: dict,
    current_time: datetime,
) -> None:
    (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    ) = repositories

    customer_repository.get_by_reference.return_value = customer
    confirmation_repository.consume.side_effect = ConfirmationRequiredError(
        "Confirmation has not been approved."
    )

    with pytest.raises(ConfirmationRequiredError):
        service.create_dispute(
            identity,
            confirmation_id="CONF-pending",
            category=approved_request["category"],
            description=approved_request["description"],
            correlation_id="CORR-002",
            now=current_time,
        )

    dispute_repository.add.assert_not_called()
    audit_repository.record.assert_not_called()
    dispute_repository.db.rollback.assert_called_once()


def test_altered_payload_has_a_different_confirmation_hash(
    approved_request: dict,
) -> None:
    altered_request = {
        **approved_request,
        "description": "Customer reports a different transaction.",
    }

    assert hash_confirmation_payload(altered_request) != (
        hash_confirmation_payload(approved_request)
    )


def test_wrong_session_prevents_dispute_creation(
    service: DisputeService,
    repositories: tuple[Mock, Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    approved_request: dict,
    current_time: datetime,
) -> None:
    (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    ) = repositories

    customer_repository.get_by_reference.return_value = customer
    confirmation_repository.consume.side_effect = CustomerMismatchError(
        "Confirmation does not belong to this customer session."
    )

    with pytest.raises(CustomerMismatchError):
        service.create_dispute(
            identity,
            confirmation_id="CONF-other-session",
            category=approved_request["category"],
            description=approved_request["description"],
            correlation_id="CORR-003",
            now=current_time,
        )

    dispute_repository.add.assert_not_called()
    audit_repository.record.assert_not_called()
    dispute_repository.db.rollback.assert_called_once()


def test_replayed_confirmation_prevents_dispute_creation(
    service: DisputeService,
    repositories: tuple[Mock, Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    approved_request: dict,
    current_time: datetime,
) -> None:
    (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    ) = repositories

    customer_repository.get_by_reference.return_value = customer
    confirmation_repository.consume.side_effect = ConfirmationRequiredError(
        "Confirmation has already been used."
    )

    with pytest.raises(ConfirmationRequiredError):
        service.create_dispute(
            identity,
            confirmation_id="CONF-already-used",
            category=approved_request["category"],
            description=approved_request["description"],
            correlation_id="CORR-004",
            now=current_time,
        )

    dispute_repository.add.assert_not_called()
    audit_repository.record.assert_not_called()
    dispute_repository.db.rollback.assert_called_once()


def test_database_failure_rolls_back_dispute_workflow(
    service: DisputeService,
    repositories: tuple[Mock, Mock, Mock, Mock],
    identity: CustomerIdentity,
    customer: Customer,
    approved_request: dict,
    current_time: datetime,
) -> None:
    (
        dispute_repository,
        customer_repository,
        confirmation_repository,
        audit_repository,
    ) = repositories

    customer_repository.get_by_reference.return_value = customer
    audit_repository.record.side_effect = RuntimeError("Audit insert failed")

    with pytest.raises(RuntimeError, match="Audit insert failed"):
        service.create_dispute(
            identity,
            confirmation_id="CONF-approved",
            category=approved_request["category"],
            description=approved_request["description"],
            correlation_id="CORR-005",
            now=current_time,
        )

    confirmation_repository.consume.assert_called_once()
    dispute_repository.add.assert_called_once()
    audit_repository.record.assert_called_once()
    dispute_repository.db.rollback.assert_called_once()


