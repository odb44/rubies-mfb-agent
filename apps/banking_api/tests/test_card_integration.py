"""PostgreSQL integration tests for confirmation-protected card blocking."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from rubies_banking_api.models.audit_log import AuditLog
from rubies_banking_api.models.card import Card
from rubies_banking_api.models.confirmation import Confirmation
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.card_repository import CardRepository
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.services.card_service import CardService
from rubies_banking_api.services.confirmation_service import ConfirmationService
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
    """Create isolated synthetic customer, card, and workflow services."""
    suffix = uuid4().hex[:12].upper()
    customer_reference = f"IT-{suffix}"
    card_reference = f"CARD-{suffix}"
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

    card = Card(
        customer_id=customer.id,
        card_reference=card_reference,
        masked_number="**** **** **** 1234",
        card_type="DEBIT",
        status="ACTIVE",
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)

    confirmation_repository = ConfirmationRepository(db_session)
    confirmation_service = ConfirmationService(confirmation_repository)

    card_service = CardService(
        card_repository=CardRepository(db_session),
        customer_repository=CustomerRepository(db_session),
        confirmation_repository=confirmation_repository,
        audit_repository=AuditRepository(db_session),
    )

    payload = {"card_reference": card_reference}

    def create_approved_confirmation():
        now = datetime.now(UTC)

        confirmation = confirmation_service.create(
            identity,
            action="BLOCK_CARD",
            payload=payload,
            now=now,
        )
        db_session.commit()

        confirmation_service.approve(
            identity,
            confirmation_id=confirmation.confirmation_id,
            action="BLOCK_CARD",
            payload=payload,
            now=now,
        )
        db_session.commit()

        return confirmation

    yield {
        "session": db_session,
        "identity": identity,
        "customer": customer,
        "card": card,
        "payload": payload,
        "correlation_id": correlation_id,
        "confirmation_service": confirmation_service,
        "card_service": card_service,
        "create_approved_confirmation": create_approved_confirmation,
    }

        # Remove only records created by this test.
    db_session.rollback()
    db_session.execute(
        delete(AuditLog).where(AuditLog.correlation_id == correlation_id)
    )
    db_session.execute(
        delete(Card).where(Card.customer_id == customer.id)
    )
    db_session.execute(
        delete(Confirmation).where(
            Confirmation.customer_id == customer_reference
        )
    )
    db_session.execute(
        delete(Customer).where(Customer.id == customer.id)
    )
    db_session.commit()


def test_postgres_blocks_card_and_records_audit(workflow):
    session = workflow["session"]
    confirmation = workflow["create_approved_confirmation"]()

    card = workflow["card_service"].block_card(
        workflow["identity"],
        card_reference=workflow["card"].card_reference,
        confirmation_id=confirmation.confirmation_id,
        correlation_id=workflow["correlation_id"],
    )

    # The service flushes but leaves commit responsibility to its caller.
    assert card.status == "BLOCKED"
    session.commit()

    stored_confirmation = session.scalar(
        select(Confirmation).where(
            Confirmation.confirmation_id == confirmation.confirmation_id
        )
    )
    assert stored_confirmation is not None
    assert stored_confirmation.status == "CONSUMED"

    stored_card = session.scalar(
        select(Card).where(Card.id == workflow["card"].id)
    )
    assert stored_card is not None
    assert stored_card.status == "BLOCKED"

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.correlation_id == workflow["correlation_id"])
    )
    assert audit_count == 1


def test_postgres_rejects_missing_card_confirmation(workflow):
    with pytest.raises(ConfirmationRequiredError):
        workflow["card_service"].block_card(
            workflow["identity"],
            card_reference=workflow["card"].card_reference,
            confirmation_id="CONF-NONEXISTENT",
            correlation_id=workflow["correlation_id"],
        )

    session = workflow["session"]
    session.rollback()
    session.refresh(workflow["card"])
    assert workflow["card"].status == "ACTIVE"


def test_postgres_rejects_card_confirmation_from_another_session(workflow):
    confirmation = workflow["create_approved_confirmation"]()
    original_identity = workflow["identity"]

    other_identity = CustomerIdentity(
        customer_id=original_identity.customer_id,
        session_id="DIFFERENT-SESSION",
        verified=True,
    )

    with pytest.raises(CustomerMismatchError):
        workflow["card_service"].block_card(
            other_identity,
            card_reference=workflow["card"].card_reference,
            confirmation_id=confirmation.confirmation_id,
            correlation_id=workflow["correlation_id"],
        )

    session = workflow["session"]
    session.rollback()
    session.refresh(workflow["card"])
    assert workflow["card"].status == "ACTIVE"


def test_postgres_rejects_confirmation_for_another_card(workflow):
    session = workflow["session"]
    confirmation = workflow["create_approved_confirmation"]()

    other_card = Card(
        customer_id=workflow["customer"].id,
        card_reference=f"CARD-OTHER-{uuid4().hex[:8].upper()}",
        masked_number="**** **** **** 5678",
        card_type="DEBIT",
        status="ACTIVE",
    )
    session.add(other_card)
    session.commit()

    with pytest.raises(ConfirmationRequiredError):
        workflow["card_service"].block_card(
            workflow["identity"],
            card_reference=other_card.card_reference,
            confirmation_id=confirmation.confirmation_id,
            correlation_id=workflow["correlation_id"],
        )

    session.rollback()
    session.refresh(other_card)
    assert other_card.status == "ACTIVE"


def test_postgres_rejects_replayed_card_confirmation(workflow):
    session = workflow["session"]
    confirmation = workflow["create_approved_confirmation"]()

    workflow["card_service"].block_card(
        workflow["identity"],
        card_reference=workflow["card"].card_reference,
        confirmation_id=confirmation.confirmation_id,
        correlation_id=workflow["correlation_id"],
    )
    session.commit()

    with pytest.raises(ConfirmationAlreadyConsumedError):
        workflow["card_service"].block_card(
            workflow["identity"],
            card_reference=workflow["card"].card_reference,
            confirmation_id=confirmation.confirmation_id,
            correlation_id=f"{workflow['correlation_id']}-REPLAY",
        )

    session.rollback()

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.correlation_id == workflow["correlation_id"])
    )
    assert audit_count == 1


def test_postgres_rolls_back_card_and_confirmation_on_audit_failure(workflow):
    session = workflow["session"]
    confirmation = workflow["create_approved_confirmation"]()

    workflow["card_service"].audit_repository.record = (
        lambda event: (_ for _ in ()).throw(RuntimeError("Simulated audit failure"))
    )

    with pytest.raises(RuntimeError, match="Simulated audit failure"):
        workflow["card_service"].block_card(
            workflow["identity"],
            card_reference=workflow["card"].card_reference,
            confirmation_id=confirmation.confirmation_id,
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

    stored_card = session.scalar(
        select(Card).where(Card.id == workflow["card"].id)
    )
    assert stored_card is not None
    assert stored_card.status == "ACTIVE"

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.correlation_id == workflow["correlation_id"])
    )
    assert audit_count == 0


def test_lists_only_authenticated_customers_cards(workflow):
    cards = workflow["card_service"].list_customer_cards(
        workflow["identity"]
    )

    assert len(cards) == 1
    assert cards[0].card_reference == workflow["card"].card_reference
    assert cards[0].masked_number == "**** **** **** 1234"
    assert cards[0].status == "ACTIVE"