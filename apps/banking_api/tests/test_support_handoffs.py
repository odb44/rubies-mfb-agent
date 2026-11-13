"""Tests for customer support handoff endpoints."""

from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from rubies_banking_api.api.dependencies import (
    get_customer_identity,
)
from rubies_banking_api.db.database import get_db
from rubies_banking_api.main import app
from rubies_banking_api.models.support_handoff import (
    HandoffPriority,
    HandoffRoute,
    HandoffStatus,
)

client = TestClient(app)


def test_create_support_handoff_returns_pending_acknowledgement():
    """A queued handoff must not claim a human has acknowledged it."""
    identity = Mock()
    db = Mock()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_customer_identity] = lambda: identity

    handoff = Mock()
    handoff.reference = "HND-TEST123"
    handoff.status = HandoffStatus.PENDING_ACKNOWLEDGEMENT.value
    handoff.priority = HandoffPriority.P3.value
    handoff.route = HandoffRoute.GENERAL_HUMAN_SUPPORT.value
    handoff.reason = "Unresolved customer issue"
    handoff.summary = "The customer needs assistance with an unresolved issue."
    handoff.created_at = "2026-10-27T10:00:00Z"
    handoff.updated_at = "2026-10-27T10:00:00Z"
    handoff.acknowledged_at = None
    handoff.acknowledgement_reference = None
    handoff.failure_reason = None

    try:
        with patch(
            "rubies_banking_api.api.support_handoffs._build_service"
        ) as build_service:
            service = build_service.return_value
            service.create.return_value = handoff

            response = client.post(
                "/api/support-handoffs",
                json={
                    "reason": "Unresolved customer issue",
                    "summary": (
                        "The customer needs assistance with an unresolved issue."
                    ),
                    "route": "GENERAL_HUMAN_SUPPORT",
                    "priority": "P3",
                    "actions_attempted": ["Provided troubleshooting guidance"],
                    "unresolved_questions": ["How can the issue be resolved?"],
                },
            )

        assert response.status_code == 201
        assert response.json()["status"] == "PENDING_ACKNOWLEDGEMENT"
        assert response.json()["acknowledged_at"] is None
        assert response.json()["acknowledgement_reference"] is None

        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(handoff)
    finally:
        app.dependency_overrides.clear()