
"""Tests for staff-only Support Desk read endpoints."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from rubies_banking_api.api.support_staff_dependencies import (
    SupportStaffIdentity,
    get_support_staff_identity,
)
from rubies_banking_api.config import get_settings
from rubies_banking_api.db.database import get_db
from rubies_banking_api.main import app

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)

STAFF_IDENTITY = SupportStaffIdentity(
    staff_number="STF-000001",
    session_id="test-staff-session",
)


def make_customer():
    return SimpleNamespace(
        id=1,
        customer_reference="CUS-000001",
        full_name="Test Customer",
    )


def make_dispute():
    return SimpleNamespace(
        case_reference="DSP-TEST001",
        customer_id=1,
        customer=make_customer(),
        transaction_id=None,
        category="OTHER_OR_UNCLEAR",
        description="Customer reported an unresolved issue.",
        status="OPEN",
        created_at=NOW,
        updated_at=NOW,
    )


def make_handoff():
    return SimpleNamespace(
        reference="HND-TEST001",
        customer_id=1,
        customer=make_customer(),
        status="PENDING_ACKNOWLEDGEMENT",
        priority="P3",
        route="GENERAL_HUMAN_SUPPORT",
        reason="Unresolved issue",
        summary="Customer requires human assistance.",
        actions_attempted=["Provided troubleshooting guidance"],
        unresolved_questions=["What is the next step?"],
        correlation_id="corr-test-001",
        failure_reason=None,
        acknowledgement_reference=None,
        created_at=NOW,
        updated_at=NOW,
        acknowledged_at=None,
    )


def make_staff_token():
    settings = get_settings()
    settings.validate_jwt_configuration()

    now = int(datetime.now(UTC).timestamp())

    return jwt.encode(
        {
            "sub": "STF-000001",
            "sid": "test-staff-session",
            "verified": True,
            "token_use": "support_staff",
            "iat": now,
            "exp": now + 900,
            "iss": settings.jwt_issuer,
            "aud": "rubies-mfb-support-desk",
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )


def test_support_desk_requires_authentication():
    """Both endpoints reject requests without staff credentials."""
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        disputes = client.get("/api/support-desk/disputes")
        handoffs = client.get("/api/support-desk/handoffs")

    assert disputes.status_code == 401
    assert handoffs.status_code == 401


def test_customer_token_cannot_access_support_desk():
    """A customer-scoped JWT must not grant support staff access."""
    app.dependency_overrides.clear()

    settings = get_settings()
    settings.validate_jwt_configuration()

    now = int(datetime.now(UTC).timestamp())

    customer_token = jwt.encode(
        {
            "sub": "CUS-000001",
            "sid": "customer-session",
            "verified": True,
            "token_use": "customer",
            "iat": now,
            "exp": now + 900,
            "iss": settings.jwt_issuer,
            "aud": "rubies-mfb-banking-api",
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    headers = {"Authorization": f"Bearer {customer_token}"}

    with TestClient(app) as client:
        disputes = client.get(
            "/api/support-desk/disputes",
            headers=headers,
        )
        handoffs = client.get(
            "/api/support-desk/handoffs",
            headers=headers,
        )

    assert disputes.status_code == 401
    assert handoffs.status_code == 401


def test_staff_can_list_disputes_with_customer_details():
    """Staff can read disputes across customers."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_support_staff_identity] = (
        lambda: STAFF_IDENTITY
    )

    try:
        with patch(
            "rubies_banking_api.api.support_desk.DisputeRepository"
        ) as repository_class:
            repository = repository_class.return_value
            repository.list_all.return_value = [make_dispute()]

            with TestClient(app) as client:
                response = client.get(
                    "/api/support-desk/disputes?limit=10&offset=0"
                )

            repository.list_all.assert_called_once_with(
                limit=10,
                offset=0,
            )

        assert response.status_code == 200

        body = response.json()

        assert body["limit"] == 10
        assert body["offset"] == 0
        assert len(body["items"]) == 1

        dispute = body["items"][0]

        assert dispute["case_reference"] == "DSP-TEST001"
        assert dispute["customer_id"] == 1
        assert dispute["customer_reference"] == "CUS-000001"
        assert dispute["customer_name"] == "Test Customer"
        assert dispute["status"] == "OPEN"

    finally:
        app.dependency_overrides.clear()


def test_staff_can_list_handoffs_with_customer_details():
    """Staff can read human escalations across customers."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_support_staff_identity] = (
        lambda: STAFF_IDENTITY
    )

    try:
        with patch(
            "rubies_banking_api.api.support_desk.SupportHandoffRepository"
        ) as repository_class:
            repository = repository_class.return_value
            repository.list_all.return_value = [make_handoff()]

            with TestClient(app) as client:
                response = client.get(
                    "/api/support-desk/handoffs?limit=5&offset=10"
                )

            repository.list_all.assert_called_once_with(
                limit=5,
                offset=10,
            )

        assert response.status_code == 200

        body = response.json()

        assert body["limit"] == 5
        assert body["offset"] == 10
        assert len(body["items"]) == 1

        handoff = body["items"][0]

        assert handoff["reference"] == "HND-TEST001"
        assert handoff["customer_reference"] == "CUS-000001"
        assert handoff["customer_name"] == "Test Customer"
        assert handoff["priority"] == "P3"
        assert handoff["status"] == "PENDING_ACKNOWLEDGEMENT"
        assert handoff["acknowledged_at"] is None

    finally:
        app.dependency_overrides.clear()


def test_support_desk_rejects_invalid_pagination():
    """Pagination parameters must stay within safe limits."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_support_staff_identity] = (
        lambda: STAFF_IDENTITY
    )

    try:
        with TestClient(app) as client:
            responses = [
                client.get("/api/support-desk/disputes?limit=0"),
                client.get("/api/support-desk/disputes?limit=101"),
                client.get("/api/support-desk/handoffs?offset=-1"),
            ]

        assert all(
            response.status_code == 422
            for response in responses
        )

    finally:
        app.dependency_overrides.clear()


def test_active_staff_with_valid_token_is_authenticated():
    """An active database-backed staff account is accepted."""
    token = make_staff_token()
    credentials = SimpleNamespace(credentials=token)

    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        staff_number="STF-000001",
        is_active=True,
    )

    identity = get_support_staff_identity(credentials, db)

    assert identity == STAFF_IDENTITY
    db.scalar.assert_called_once()


@pytest.mark.parametrize(
    "staff",
    [
        None,
        SimpleNamespace(
            staff_number="STF-000001",
            is_active=False,
        ),
    ],
    ids=["missing-staff", "inactive-staff"],
)
def test_inactive_or_missing_staff_account_is_rejected(staff):
    """A valid JWT cannot authorize a missing or inactive staff account."""
    token = make_staff_token()
    credentials = SimpleNamespace(credentials=token)

    db = MagicMock()

    # The actual database query filters for active staff.
    # Therefore, an inactive record must produce None.
    db.scalar.return_value = (
        staff if staff is not None and staff.is_active else None
    )

    with pytest.raises(HTTPException) as exc_info:
        get_support_staff_identity(credentials, db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "The support staff account is inactive or unavailable."
    )
    db.scalar.assert_called_once()
