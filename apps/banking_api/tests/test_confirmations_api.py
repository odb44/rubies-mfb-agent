
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.main import app
from rubies_security.confirmations import (
    ConfirmationExpiredError,
    ConfirmationRequiredError,
)
from rubies_security.identity import CustomerMismatchError
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
def confirmation_service(monkeypatch):
    service = Mock()
    monkeypatch.setattr(
        "rubies_banking_api.api.confirmations.get_confirmation_service",
        lambda db: service,
    )
    return service


def test_create_dispute_confirmation_returns_200(
    client,
    db_session,
    confirmation_service,
    identity,
):
    confirmation = Mock()
    confirmation.confirmation_id = "CONF-DISPUTE-001"
    confirmation.action = "OPEN_DISPUTE"
    confirmation.status = "PENDING"
    confirmation.expires_at = datetime(
        2026, 10, 25, 12, 5, tzinfo=UTC
    )
    confirmation_service.create.return_value = confirmation

    response = client.post(
        "/api/confirmations",
        json={
            "action": "OPEN_DISPUTE",
            "payload": {
                "category": " duplicate_debit ",
                "description": "  Customer reports a duplicate debit.  ",
                "transaction_reference": " DEMO-DUP-B-003 ",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["confirmation_id"] == "CONF-DISPUTE-001"
    assert response.json()["action"] == "OPEN_DISPUTE"
    assert response.json()["status"] == "PENDING"

    confirmation_service.create.assert_called_once_with(
        identity,
        action="OPEN_DISPUTE",
        payload={
            "category": "DUPLICATE_DEBIT",
            "description": "Customer reports a duplicate debit.",
            "transaction_reference": "DEMO-DUP-B-003",
        },
        now=confirmation_service.create.call_args.kwargs["now"],
    )
    db_session.commit.assert_called_once()


def test_approve_confirmation_returns_200(
    client,
    db_session,
    confirmation_service,
):
    confirmation = Mock()
    confirmation.confirmation_id = "CONF-001"
    confirmation.action = "BLOCK_CARD"
    confirmation.status = "APPROVED"
    confirmation_service.approve.return_value = confirmation

    response = client.post(
        "/api/confirmations/approve",
        json={
            "confirmation_id": "CONF-001",
            "action": "BLOCK_CARD",
            "payload": {"card_reference": "CARD-001"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "confirmation_id": "CONF-001",
        "action": "BLOCK_CARD",
        "status": "APPROVED",
    }
    confirmation_service.approve.assert_called_once()
    db_session.commit.assert_called_once()


def test_approve_dispute_confirmation_uses_normalized_payload(
    client,
    db_session,
    confirmation_service,
):
    confirmation = Mock()
    confirmation.confirmation_id = "CONF-DISPUTE-002"
    confirmation.action = "OPEN_DISPUTE"
    confirmation.status = "APPROVED"
    confirmation_service.approve.return_value = confirmation

    response = client.post(
        "/api/confirmations/approve",
        json={
            "confirmation_id": "CONF-DISPUTE-002",
            "action": "OPEN_DISPUTE",
            "payload": {
                "category": " duplicate_debit ",
                "description": "  Customer reports a duplicate debit.  ",
                "transaction_reference": " DEMO-DUP-B-003 ",
            },
        },
    )

    assert response.status_code == 200

    call_arguments = confirmation_service.approve.call_args.kwargs

    assert call_arguments["confirmation_id"] == "CONF-DISPUTE-002"
    assert call_arguments["action"] == "OPEN_DISPUTE"
    assert call_arguments["payload"] == {
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reports a duplicate debit.",
        "transaction_reference": "DEMO-DUP-B-003",
    }

    db_session.commit.assert_called_once()


def test_dispute_confirmation_without_transaction_reference_is_valid(
    client,
    db_session,
    confirmation_service,
):
    confirmation = Mock()
    confirmation.confirmation_id = "CONF-DISPUTE-003"
    confirmation.action = "OPEN_DISPUTE"
    confirmation.status = "PENDING"
    confirmation.expires_at = datetime(
        2026, 10, 25, 12, 5, tzinfo=UTC
    )
    confirmation_service.create.return_value = confirmation

    response = client.post(
        "/api/confirmations",
        json={
            "action": "OPEN_DISPUTE",
            "payload": {
                "category": "DUPLICATE_DEBIT",
                "description": "Customer reports a duplicate debit.",
            },
        },
    )

    assert response.status_code == 200

    call_arguments = confirmation_service.create.call_args.kwargs

    assert call_arguments["payload"] == {
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reports a duplicate debit.",
    }
    assert "transaction_reference" not in call_arguments["payload"]

    db_session.commit.assert_called_once()


def test_dispute_confirmation_rejects_unsupported_payload_fields(
    client,
    db_session,
    confirmation_service,
):
    response = client.post(
        "/api/confirmations",
        json={
            "action": "OPEN_DISPUTE",
            "payload": {
                "category": "DUPLICATE_DEBIT",
                "description": "Customer reports a duplicate debit.",
                "transaction_id": "123",
            },
        },
    )

    assert response.status_code == 422
    confirmation_service.create.assert_not_called()
    db_session.commit.assert_not_called()


def test_dispute_approval_rejects_blank_transaction_reference(
    client,
    db_session,
    confirmation_service,
):
    response = client.post(
        "/api/confirmations/approve",
        json={
            "confirmation_id": "CONF-DISPUTE-004",
            "action": "OPEN_DISPUTE",
            "payload": {
                "category": "DUPLICATE_DEBIT",
                "description": "Customer reports a duplicate debit.",
                "transaction_reference": "   ",
            },
        },
    )

    assert response.status_code == 422
    confirmation_service.approve.assert_not_called()
    db_session.commit.assert_not_called()


def test_approve_expired_confirmation_returns_409_and_commits_expiry(
    client,
    db_session,
    confirmation_service,
):
    confirmation_service.approve.side_effect = ConfirmationExpiredError(
        "Confirmation has expired."
    )

    response = client.post(
        "/api/confirmations/approve",
        json={
            "confirmation_id": "CONF-EXPIRED",
            "action": "BLOCK_CARD",
            "payload": {"card_reference": "CARD-001"},
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "This confirmation has expired. Create a new confirmation to continue."
    )
    db_session.commit.assert_called_once()
    db_session.rollback.assert_not_called()


def test_approve_invalid_confirmation_returns_409_and_rolls_back(
    client,
    db_session,
    confirmation_service,
):
    confirmation_service.approve.side_effect = ConfirmationRequiredError(
        "Confirmation does not authorize this action."
    )

    response = client.post(
        "/api/confirmations/approve",
        json={
            "confirmation_id": "CONF-INVALID",
            "action": "BLOCK_CARD",
            "payload": {"card_reference": "CARD-001"},
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Confirmation does not authorize this action."
    )
    db_session.rollback.assert_called_once()
    db_session.commit.assert_not_called()


def test_approve_confirmation_from_another_session_returns_403(
    client,
    db_session,
    confirmation_service,
):
    confirmation_service.approve.side_effect = CustomerMismatchError(
        "Confirmation does not belong to this customer session."
    )

    response = client.post(
        "/api/confirmations/approve",
        json={
            "confirmation_id": "CONF-OTHER-SESSION",
            "action": "BLOCK_CARD",
            "payload": {"card_reference": "CARD-001"},
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "This confirmation is not available to the authenticated customer."
    )
    db_session.rollback.assert_called_once()
    db_session.commit.assert_not_called()
