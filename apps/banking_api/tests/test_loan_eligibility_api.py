
"""API tests for loan eligibility assessments."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.main import app
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity

ENDPOINT = "/api/loans/eligibility/check"


@pytest.fixture
def db_session():
    return Mock()


@pytest.fixture
def identity():
    return CustomerIdentity(
        customer_id="CUST-001",
        session_id="SESSION-001",
        verified=True,
    )


@pytest.fixture
def client(db_session, identity):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_customer_identity] = lambda: identity

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def eligibility_service(monkeypatch):
    service = Mock()

    monkeypatch.setattr(
        "rubies_banking_api.api.loan_eligibility._build_service",
        lambda db: service,
    )

    return service


@pytest.fixture
def eligible_assessment():
    return SimpleNamespace(
        result="ELIGIBLE_FOR_REVIEW",
        product_code="SALARY_ADVANCE",
        requested_amount=Decimal("100000.00"),
        term_months=2,
        currency="NGN",
        disposable_income=Decimal("80000.00"),
        estimated_monthly_principal=Decimal("50000.00"),
        reason_codes=("AFFORDABILITY_PASSED",),
        explanation=(
            "The applicant meets the current preliminary "
            "eligibility rules and may proceed for review."
        ),
        policy_document_id="RB-POL-LOAN-001",
        policy_version="0.2",
        ruleset_version="loan-eligibility-v0.2",
        assessed_at=datetime.now(UTC),
        correlation_id="test-correlation-id",
    )


@pytest.fixture
def valid_payload():
    return {
        "product_code": "SALARY_ADVANCE",
        "requested_amount": "100000.00",
        "term_months": 2,
    }


def test_check_loan_eligibility_returns_assessment(
    client,
    db_session,
    identity,
    eligibility_service,
    eligible_assessment,
    valid_payload,
):
    eligibility_service.assess_eligibility.return_value = (
        eligible_assessment
    )

    response = client.post(ENDPOINT, json=valid_payload)

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["result"] == "ELIGIBLE_FOR_REVIEW"
    assert body["product_code"] == "SALARY_ADVANCE"
    assert body["requested_amount"] == "100000.00"
    assert body["term_months"] == 2
    assert body["currency"] == "NGN"
    assert body["disposable_income"] == "80000.00"
    assert body["estimated_monthly_principal"] == "50000.00"
    assert body["reason_codes"] == ["AFFORDABILITY_PASSED"]
    assert body["policy_document_id"] == "RB-POL-LOAN-001"
    assert body["policy_version"] == "0.2"
    assert body["ruleset_version"] == "loan-eligibility-v0.2"

    args, kwargs = eligibility_service.assess_eligibility.call_args

    assert args[0] == identity
    assert kwargs["product_code"] == "SALARY_ADVANCE"
    assert kwargs["requested_amount"] == Decimal("100000.00")
    assert kwargs["term_months"] == 2
    assert kwargs["correlation_id"]

    db_session.commit.assert_called_once()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "product_code": "SALARY_ADVANCE",
            "requested_amount": "0.00",
            "term_months": 2,
        },
        {
            "product_code": "SALARY_ADVANCE",
            "requested_amount": "-1000.00",
            "term_months": 2,
        },
        {
            "product_code": "SALARY_ADVANCE",
            "requested_amount": "100000.00",
            "term_months": 0,
        },
        {
            "product_code": "SALARY_ADVANCE",
            "requested_amount": "100000.00",
            "term_months": 2,
            "unexpected_field": "not-allowed",
        },
    ],
)
def test_check_loan_eligibility_rejects_invalid_requests(
    client,
    eligibility_service,
    payload,
):
    response = client.post(ENDPOINT, json=payload)

    assert response.status_code == 422
    eligibility_service.assess_eligibility.assert_not_called()


def test_check_loan_eligibility_rejects_unverified_identity(
    client,
    db_session,
    eligibility_service,
    valid_payload,
):
    eligibility_service.assess_eligibility.side_effect = (
        IdentityVerificationError("Identity not verified")
    )

    response = client.post(ENDPOINT, json=valid_payload)

    assert response.status_code == 401
    db_session.commit.assert_not_called()
    db_session.rollback.assert_called_once()


def test_check_loan_eligibility_rejects_customer_mismatch(
    client,
    db_session,
    eligibility_service,
    valid_payload,
):
    eligibility_service.assess_eligibility.side_effect = (
        CustomerMismatchError("Customer ownership mismatch")
    )

    response = client.post(ENDPOINT, json=valid_payload)

    assert response.status_code == 403
    db_session.commit.assert_not_called()
    db_session.rollback.assert_called_once()


def test_check_loan_eligibility_handles_service_validation_error(
    client,
    db_session,
    eligibility_service,
    valid_payload,
):
    eligibility_service.assess_eligibility.side_effect = ValueError(
        "Invalid eligibility assessment input."
    )

    response = client.post(ENDPOINT, json=valid_payload)

    assert response.status_code == 422
    db_session.commit.assert_not_called()
    db_session.rollback.assert_called_once()


def test_check_loan_eligibility_rolls_back_on_unexpected_error(
    db_session,
    identity,
    eligibility_service,
    valid_payload,
):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_customer_identity] = lambda: identity

    eligibility_service.assess_eligibility.side_effect = RuntimeError(
        "Unexpected assessment failure"
    )

    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post(ENDPOINT, json=valid_payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    db_session.commit.assert_not_called()
    db_session.rollback.assert_called_once()


def test_check_loan_eligibility_requires_authentication():
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.post(
            ENDPOINT,
            json={
                "product_code": "SALARY_ADVANCE",
                "requested_amount": "100000.00",
                "term_months": 2,
            },
        )

    assert response.status_code == 401

