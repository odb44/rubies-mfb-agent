"""Integration tests for request-token handling in the FastAPI application."""

from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from rubies_agent.app import require_authenticated_customer
from rubies_agent.runtime import _get_request_access_token
from rubies_banking_api.api.dependencies import get_customer_identity


def create_test_app() -> FastAPI:
    """Build a small app using the production authentication dependency."""
    app = FastAPI()

    app.dependency_overrides[get_customer_identity] = lambda: SimpleNamespace(
        customer_id="customer-001",
        session_id="session-001",
    )

    @app.get("/protected")
    async def protected(
        identity=Depends(require_authenticated_customer),  # noqa: B008
    ) -> dict[str, str]:
        return {
            "customer_id": identity.customer_id,
            "session_id": identity.session_id,
            "request_token": _get_request_access_token(),
        }

    return app


def test_authenticated_request_scopes_token_to_request() -> None:
    """The current request should see its own bearer token."""
    app = create_test_app()

    with TestClient(app) as client:
        response = client.get(
            "/protected",
            headers={"Authorization": "Bearer test-customer-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "customer_id": "customer-001",
        "session_id": "session-001",
        "request_token": "test-customer-token",
    }

    with pytest.raises(RuntimeError):
        _get_request_access_token()


def test_missing_bearer_header_is_rejected() -> None:
    """The endpoint must reject requests without a bearer token."""
    with TestClient(create_test_app()) as client:
        response = client.get("/protected")

    assert response.status_code == 401
    assert response.json()["detail"] == "A valid bearer token is required."