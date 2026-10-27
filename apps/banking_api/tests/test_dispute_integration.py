"""PostgreSQL integration tests for confirmation-protected disputes."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from rubies_banking_api.models.audit_log import AuditLog
from rubies_banking_api.models.confirmation import Confirmation
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.models.dispute import Dispute
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.repositories.dispute_repository import DisputeRepository
from rubies_banking_api.services.confirmation_service import ConfirmationService
from rubies_banking_api.services.dispute_service import DisputeService
from rubies_security.confirmations import (
    ConfirmationAlreadyConsumedError,
    ConfirmationRequiredError,
)
from rubies_security.identity import CustomerMismatchError
from rubies_shared.identity import CustomerIdentity
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_NAME = "rubies_mfb_test"


@pytest.fixture
def db_session():
    """Create a session only when an explicit test database URL is supplied."""
    database_url = os.environ.get("TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests.")

    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            database_name = connection.scalar(text("SELECT current_database()"))

        if database_name != TEST_DATABASE_NAME:
            pytest.fail(
                f"Integration tests require {TEST_DATABASE_NAME!r}; "
                f"received {database_name!r}. No test data was written."
            )

        factory = sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
        )

        with factory() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def workflow(db_session: Session):
    """Create isolated synthetic customer and workflow services."""
    suffix = uuid4().hex[:12].upper()
    customer_reference = f"IT-{suffix}"
    correlation_id = f"CORR-{suffix}"
    identity = CustomerIdentity(
        customer_id=customer_reference,
        session_id=f"SESSION-{suffix}",
        verified=True,
    )

    customer = Customer(
        customer_reference=customer_reference,
        full_name="Integration Test Customer",
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    confirmation_repository = ConfirmationRepository(db_session)
    confirmation_service = ConfirmationService(confirmation_repository)

    dispute_service = DisputeService(
        dispute_repository=DisputeRepository(db_session),
        customer_repository=CustomerRepository(db_session),
        confirmation_repository=confirmation_repository,
        audit_repository=AuditRepository(db_session),
    )

    payload = {
        "category": "DUPLICATE_DEBIT",
        "description": "Synthetic integration test dispute.",
        "transaction_id": None,
    }

    def create_approved_confirmation():
        now = datetime.now(UTC)
        confirmation = confirmation_service.create(
            identity,
            action="OPEN_DISPUTE",
            payload=payload,
            now=now,
        )
        db_session.commit()

        confirmation_service.approve(
            identity,
            confirmation_id=confirmation.confirmation_id,
            action="OPEN_DISPUTE",
            payload=payload,
            now=now,
        )
        db_session.commit()

        return confirmation

    yield {
        "session": db_session,
        "identity": identity,
        "customer": customer,
        "payload": payload,
        "correlation_id": correlation_id,
        "confirmation_service": confirmation_service,
        "dispute_service": dispute_service,
        "create_approved_confirmation": create_approved_confirmation,
    }

    # Remove only rows created by this test.
    db_session.rollback()
    db_session.execute(
        delete(AuditLog).where(AuditLog.correlation_id == correlation_id)
    )
    db_session.execute(
        delete(Dispute).where(Dispute.customer_id == customer.id)
    )
    db_session.execute(
        delete(Confirmation).where(
            Confirmation.customer_id == customer_reference
        )
    )
    db_session.execute(delete(Customer).where(Customer.id == customer.id))
    db_session.commit()


def test_postgres_confirmation_approval_and_consumption(workflow):
    session = workflow["session"]
    identity = workflow["identity"]
    confirmation = workflow["create_approved_confirmation"]()

    stored = session.scalar(
        select(Confirmation).where(
            Confirmation.confirmation_id == confirmation.confirmation_id
        )
    )
    assert stored is not None
    assert stored.status == "APPROVED"

    dispute = workflow["dispute_service"].create_dispute(
        identity,
        confirmation_id=confirmation.confirmation_id,
        category=workflow["payload"]["category"],
        description=workflow["payload"]["description"],
        correlation_id=workflow["correlation_id"],
    )
    session.commit()

    session.refresh(stored)
    assert stored.status == "CONSUMED"
    assert dispute.status == "OPEN"

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.correlation_id == workflow["correlation_id"])
    )
    assert audit_count == 1


def test_postgres_rejects_altered_payload(workflow):
    confirmation = workflow["create_approved_confirmation"]()
    altered_payload = {
        **workflow["payload"],
        "description": "A different dispute description.",
    }

    with pytest.raises(ConfirmationRequiredError):
        workflow["confirmation_service"].approve(
            workflow["identity"],
            confirmation_id=confirmation.confirmation_id,
            action="OPEN_DISPUTE",
            payload=altered_payload,
        )

    workflow["session"].rollback()


def test_postgres_rejects_confirmation_from_another_session(workflow):
    confirmation = workflow["create_approved_confirmation"]()
    original_identity = workflow["identity"]

    other_identity = CustomerIdentity(
        customer_id=original_identity.customer_id,
        session_id="DIFFERENT-SESSION",
        verified=True,
    )

    with pytest.raises(CustomerMismatchError):
        workflow["confirmation_service"].approve(
            other_identity,
            confirmation_id=confirmation.confirmation_id,
            action="OPEN_DISPUTE",
            payload=workflow["payload"],
        )

    workflow["session"].rollback()


def test_postgres_rejects_replayed_confirmation(workflow):
    session = workflow["session"]
    identity = workflow["identity"]
    confirmation = workflow["create_approved_confirmation"]()

    workflow["dispute_service"].create_dispute(
        identity,
        confirmation_id=confirmation.confirmation_id,
        category=workflow["payload"]["category"],
        description=workflow["payload"]["description"],
        correlation_id=workflow["correlation_id"],
    )
    session.commit()

    with pytest.raises(ConfirmationAlreadyConsumedError):
        workflow["dispute_service"].create_dispute(
            identity,
            confirmation_id=confirmation.confirmation_id,
            category=workflow["payload"]["category"],
            description=workflow["payload"]["description"],
            correlation_id=f"{workflow['correlation_id']}-REPLAY",
        )

    session.rollback()

    dispute_count = session.scalar(
        select(func.count())
        .select_from(Dispute)
        .where(Dispute.customer_id == workflow["customer"].id)
    )
    assert dispute_count == 1


def test_postgres_rolls_back_confirmation_and_dispute_on_audit_failure(
    workflow,
):
    session = workflow["session"]
    identity = workflow["identity"]
    confirmation = workflow["create_approved_confirmation"]()

    # Replace only this service instance's audit repository with one that fails.
    workflow["dispute_service"].audit_repository.record = (
        lambda event: (_ for _ in ()).throw(RuntimeError("Simulated audit failure"))
    )

    with pytest.raises(RuntimeError, match="Simulated audit failure"):
        workflow["dispute_service"].create_dispute(
            identity,
            confirmation_id=confirmation.confirmation_id,
            category=workflow["payload"]["category"],
            description=workflow["payload"]["description"],
            correlation_id=workflow["correlation_id"],
        )

    session.rollback()

    stored_confirmation = session.scalar(
        select(Confirmation).where(
            Confirmation.confirmation_id == confirmation.confirmation_id
        )
    )
    assert stored_confirmation is not None
    assert stored_confirmation.status == "APPROVED"

    dispute_count = session.scalar(
        select(func.count())
        .select_from(Dispute)
        .where(Dispute.customer_id == workflow["customer"].id)
    )
    assert dispute_count == 0

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.correlation_id == workflow["correlation_id"])
    )
    assert audit_count == 0
    