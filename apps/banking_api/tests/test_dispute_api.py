from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.main import app
from rubies_banking_api.models.dispute import Dispute
from rubies_security.confirmations import (
    ConfirmationAlreadyConsumedError,
    ConfirmationExpiredError,
    ConfirmationRequiredError,
)
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

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def dispute_service(monkeypatch):
    service = Mock()
    monkeypatch.setattr(
        "rubies_banking_api.api.disputes._build_service",
        lambda db: service,
    )
    return service


def test_create_dispute_returns_201(client, db_session, dispute_service):
    dispute = Mock()
    dispute.case_reference = "DIS-ABC123DEF456"
    dispute.category = "DUPLICATE_DEBIT"
    dispute.description = "I was charged twice."
    dispute.status = "OPEN"
    dispute.transaction = None
    dispute.created_at = datetime.now(UTC)

    dispute_service.create_dispute.return_value = dispute

    response = client.post(
        "/api/disputes",
        json={
            "confirmation_id": "CONFIRM-001",
            "category": "DUPLICATE_DEBIT",
            "description": "I was charged twice.",
        },
    )

    assert response.status_code == 201
    assert response.json()["case_reference"] == "DIS-ABC123DEF456"
    assert response.json()["status"] == "OPEN"
    db_session.commit.assert_called_once()


def test_create_dispute_rejects_invalid_category(
    client,
    dispute_service,
):
    dispute_service.create_dispute.side_effect = ValueError(
        "Invalid dispute category."
    )

    response = client.post(
        "/api/disputes",
        json={
            "confirmation_id": "CONFIRM-001",
            "category": "INVALID_CATEGORY",
            "description": "I need help with a transaction.",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (IdentityVerificationError("Not verified"), 401),
        (CustomerMismatchError("Customer mismatch"), 403),
        (ConfirmationAlreadyConsumedError("Already used"), 409),
        (ConfirmationExpiredError("Expired"), 409),
        (ConfirmationRequiredError("Confirmation required"), 409),
    ],
)
def test_create_dispute_maps_security_errors_to_http_status(
    client,
    db_session,
    dispute_service,
    error,
    expected_status,
):
    dispute_service.create_dispute.side_effect = error

    response = client.post(
        "/api/disputes",
        json={
            "confirmation_id": "CONFIRM-001",
            "category": "DUPLICATE_DEBIT",
            "description": "I was charged twice.",
        },
    )

    assert response.status_code == expected_status
    db_session.rollback.assert_called_once()


def test_list_disputes_returns_customer_cases(
    client,
    dispute_service,
    monkeypatch,
):
    customer = Mock()
    customer.id = 1
    dispute_service.resolve_customer.return_value = customer

    dispute = Mock(spec=Dispute)
    dispute.case_reference = "DIS-ABC123DEF456"
    dispute.category = "DUPLICATE_DEBIT"
    dispute.description = "I was charged twice."
    dispute.status = "OPEN"
    dispute.transaction = None
    dispute.created_at = datetime.now(UTC)

    repository = Mock()
    repository.list_by_customer.return_value = [dispute]

    monkeypatch.setattr(
        "rubies_banking_api.api.disputes.DisputeRepository",
        lambda db: repository,
    )

    response = client.get("/api/disputes")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["case_reference"] == "DIS-ABC123DEF456"
    assert body["items"][0]["status"] == "OPEN"
    repository.list_by_customer.assert_called_once_with(
        1,
        limit=20,
        offset=0,
    )
