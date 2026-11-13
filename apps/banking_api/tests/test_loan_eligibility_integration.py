
"""PostgreSQL integration tests for loan eligibility assessments."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from rubies_banking_api.models.account import Account
from rubies_banking_api.models.audit_log import AuditLog
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.models.loan_eligibility_profile import (
    LoanEligibilityProfile,
)
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.services.loan_eligibility_service import (
    ELIGIBLE_FOR_REVIEW,
    INSUFFICIENT_DATA,
    NOT_ELIGIBLE_UNDER_CURRENT_RULES,
    LoanEligibilityService,
)
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
    """Create an isolated synthetic customer and eligibility workflow."""
    suffix = uuid4().hex[:12].upper()
    customer_reference = f"IT-{suffix}"
    account_number = f"{uuid4().int % 10**10:010d}"
    correlation_id = f"LOAN-ELIG-{suffix}"

    identity = CustomerIdentity(
        customer_id=customer_reference,
        session_id=f"SESSION-{suffix}",
        verified=True,
    )

    customer = Customer(
        customer_reference=customer_reference,
        full_name="Loan Eligibility Integration Customer",
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()

    account = Account(
        customer_id=customer.id,
        account_number=account_number,
        currency="NGN",
        balance=Decimal("500000.00"),
        status="ACTIVE",
    )
    db_session.add(account)

    profile = LoanEligibilityProfile(
        customer_id=customer.id,
        employment_type="SALARIED",
        monthly_income=Decimal("200000.00"),
        monthly_expenses=Decimal("80000.00"),
        existing_monthly_debt=Decimal("20000.00"),
        profile_source="CUSTOMER_PROVIDED",
        verification_status="VERIFIED",
        verified_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.commit()

    service = LoanEligibilityService(
        customer_repository=CustomerRepository(db_session),
        audit_repository=AuditRepository(db_session),
    )

    yield {
        "session": db_session,
        "identity": identity,
        "customer": customer,
        "account": account,
        "profile": profile,
        "service": service,
        "correlation_id": correlation_id,
    }

    # Remove only records created by this test.
    db_session.rollback()
    db_session.execute(
        delete(AuditLog).where(
            AuditLog.correlation_id == correlation_id
        )
    )
    db_session.execute(
        delete(LoanEligibilityProfile).where(
            LoanEligibilityProfile.customer_id == customer.id
        )
    )
    db_session.execute(
        delete(Account).where(Account.customer_id == customer.id)
    )
    db_session.execute(
        delete(Customer).where(Customer.id == customer.id)
    )
    db_session.commit()


def assess(workflow, amount="100000.00", term_months=2):
    return workflow["service"].assess_eligibility(
        workflow["identity"],
        product_code="SALARY_ADVANCE",
        requested_amount=Decimal(amount),
        term_months=term_months,
        correlation_id=workflow["correlation_id"],
    )


def test_postgres_assesses_eligible_customer_and_persists_audit(workflow):
    session = workflow["session"]

    assessment = assess(workflow)

    assert assessment.result == ELIGIBLE_FOR_REVIEW
    assert assessment.product_code == "SALARY_ADVANCE"
    assert assessment.requested_amount == Decimal("100000.00")
    assert assessment.term_months == 2
    assert assessment.disposable_income == Decimal("100000.00")
    assert assessment.estimated_monthly_principal == Decimal("50000.00")

    session.commit()

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.correlation_id == workflow["correlation_id"]
        )
    )

    assert audit_count == 1

    audit = session.scalar(
        select(AuditLog).where(
            AuditLog.correlation_id == workflow["correlation_id"]
        )
    )

    assert audit is not None
    assert audit.outcome == "COMPLETED"
    assert audit.details["result"] == ELIGIBLE_FOR_REVIEW
    assert audit.details["policy_version"] == "0.3"


def test_postgres_rejects_unaffordable_loan_and_persists_audit(workflow):
    session = workflow["session"]

    assessment = assess(
        workflow,
        amount="300000.00",
        term_months=2,
    )

    assert assessment.result == NOT_ELIGIBLE_UNDER_CURRENT_RULES
    assert assessment.disposable_income == Decimal("100000.00")
    assert assessment.estimated_monthly_principal == Decimal("150000.00")

    session.commit()

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.correlation_id == workflow["correlation_id"]
        )
    )

    assert audit_count == 1


def test_postgres_returns_insufficient_data_without_profile(workflow):
    session = workflow["session"]

    session.delete(workflow["profile"])
    session.commit()

    assessment = assess(workflow)

    assert assessment.result == INSUFFICIENT_DATA

    session.commit()

    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.correlation_id == workflow["correlation_id"]
        )
    )

    assert audit_count == 1
