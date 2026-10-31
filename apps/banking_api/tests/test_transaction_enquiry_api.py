"""API tests for read-only transaction enquiries."""

from datetime import UTC, datetime
from decimal import Decimal
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
def enquiry_service(monkeypatch):
    service = Mock()

    monkeypatch.setattr(
        "rubies_banking_api.api.transactions._build_service",
        lambda db: service,
    )

    return service


@pytest.fixture
def sample_account():
    account = Mock()
    account.id = 1
    account.customer_id = 1
    account.account_number = "0123456789"
    account.currency = "NGN"
    account.status = "ACTIVE"
    return account


@pytest.fixture
def sample_transaction():
    transaction = Mock()
    transaction.id = 10
    transaction.reference = "TXN-001"
    transaction.transaction_type = "DEBIT"
    transaction.amount = Decimal("5000.00")
    transaction.status = "SUCCESSFUL"
    transaction.description = "Transfer"
    transaction.created_at = datetime.now(UTC)

    account = Mock()
    account.customer_id = 1
    account.currency = "NGN"
    transaction.account = account

    return transaction


def test_get_mini_statement_returns_transactions(
    client,
    identity,
    enquiry_service,
    sample_account,
    sample_transaction,
):
    enquiry_service.get_mini_statement.return_value = (
        sample_account,
        [sample_transaction],
    )

    response = client.get(
        "/api/accounts/0123456789/mini-statement"
    )

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["account_reference"] == "0123456789"
    assert body["currency"] == "NGN"
    assert body["limit"] == 10
    assert body["offset"] == 0

    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["reference"] == "TXN-001"
    assert item["transaction_type"] == "DEBIT"
    assert item["amount"] == "5000.00"
    assert item["status"] == "SUCCESSFUL"
    assert item["description"] == "Transfer"


    args, kwargs = enquiry_service.get_mini_statement.call_args

    assert args[0] == identity
    assert kwargs["account_reference"] == "0123456789"
    assert kwargs["limit"] == 10
    assert kwargs["offset"] == 0


def test_get_mini_statement_passes_pagination(
    client,
    enquiry_service,
    sample_account,
):
    enquiry_service.get_mini_statement.return_value = (
        sample_account,
        [],
    )

    response = client.get(
        "/api/accounts/0123456789/mini-statement?limit=5&offset=10"
    )

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["items"] == []
    assert body["limit"] == 5
    assert body["offset"] == 10

    kwargs = enquiry_service.get_mini_statement.call_args.kwargs
    assert kwargs["limit"] == 5
    assert kwargs["offset"] == 10


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (51, 0),
        (10, -1),
    ],
)
def test_get_mini_statement_rejects_invalid_pagination(
    client,
    limit,
    offset,
):
    response = client.get(
        "/api/accounts/0123456789/mini-statement"
        f"?limit={limit}&offset={offset}"
    )

    assert response.status_code == 422


def test_get_mini_statement_rejects_unverified_identity(
    client,
    enquiry_service,
):
    enquiry_service.get_mini_statement.side_effect = (
        IdentityVerificationError("Identity not verified")
    )

    response = client.get(
        "/api/accounts/0123456789/mini-statement"
    )

    assert response.status_code == 401


def test_get_mini_statement_rejects_another_customers_account(
    client,
    enquiry_service,
):
    enquiry_service.get_mini_statement.side_effect = (
        CustomerMismatchError("Account ownership mismatch")
    )

    response = client.get(
        "/api/accounts/9999999999/mini-statement"
    )

    assert response.status_code == 403


def test_get_mini_statement_handles_unknown_account(
    client,
    enquiry_service,
):
    enquiry_service.get_mini_statement.side_effect = ValueError(
        "Account not found."
    )

    response = client.get(
        "/api/accounts/9999999999/mini-statement"
    )

    assert response.status_code == 404


def test_get_transaction_status_returns_transaction(
    client,
    identity,
    enquiry_service,
    sample_transaction,
):
    enquiry_service.get_transaction_status.return_value = (
        sample_transaction
    )

    response = client.get(
        "/api/transactions/TXN-001/status"
    )

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["reference"] == "TXN-001"
    assert body["status"] == "SUCCESSFUL"
    assert body["transaction_type"] == "DEBIT"
    assert body["amount"] == "5000.00"
    assert body["currency"] == "NGN"

    args, kwargs = enquiry_service.get_transaction_status.call_args

    assert args[0] == identity
    assert kwargs["transaction_reference"] == "TXN-001"

def test_get_transaction_status_rejects_unverified_identity(
    client,
    enquiry_service,
):
    enquiry_service.get_transaction_status.side_effect = (
        IdentityVerificationError("Identity not verified")
    )

    response = client.get(
        "/api/transactions/TXN-001/status"
    )

    assert response.status_code == 401


def test_get_transaction_status_rejects_another_customers_transaction(
    client,
    enquiry_service,
):
    enquiry_service.get_transaction_status.side_effect = (
        CustomerMismatchError("Transaction ownership mismatch")
    )

    response = client.get(
        "/api/transactions/TXN-OTHER/status"
    )

    assert response.status_code == 403


def test_get_transaction_status_handles_unknown_transaction(
    client,
    enquiry_service,
):
    enquiry_service.get_transaction_status.side_effect = ValueError(
        "Transaction not found."
    )

    response = client.get(
        "/api/transactions/TXN-UNKNOWN/status"
    )

    assert response.status_code == 404


def test_mini_statement_requires_authentication():
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get(
            "/api/accounts/0123456789/mini-statement"
        )

    assert response.status_code == 401


def test_transaction_status_requires_authentication():
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get(
            "/api/transactions/TXN-001/status"
        )

    assert response.status_code == 401

def test_get_my_accounts_returns_only_active_customer_accounts(
    client,
    db_session,
):
    customer = Mock()
    customer.id = 1
    customer.is_active = True

    account = Mock()
    account.account_number = "0123456789"
    account.currency = "NGN"
    account.status = "ACTIVE"

    db_session.scalar.return_value = customer
    db_session.scalars.return_value.all.return_value = [account]

    response = client.get("/api/accounts/me")

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["success"] is True
    assert body["data"]["count"] == 1
    assert body["data"]["accounts"] == [
        {
            "account_reference": "0123456789",
            "currency": "NGN",
            "status": "ACTIVE",
        }
    ]


def test_get_my_accounts_returns_empty_list_when_no_active_accounts(
    client,
    db_session,
):
    customer = Mock()
    customer.id = 1
    customer.is_active = True

    db_session.scalar.return_value = customer
    db_session.scalars.return_value.all.return_value = []

    response = client.get("/api/accounts/me")

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["success"] is True
    assert body["data"]["count"] == 0
    assert body["data"]["accounts"] == []


def test_get_my_accounts_rejects_missing_customer(
    client,
    db_session,
):
    db_session.scalar.return_value = None

    response = client.get("/api/accounts/me")

    assert response.status_code == 403


def test_get_my_accounts_rejects_inactive_customer(
    client,
    db_session,
):
    customer = Mock()
    customer.id = 1
    customer.is_active = False

    db_session.scalar.return_value = customer

    response = client.get("/api/accounts/me")

    assert response.status_code == 403    