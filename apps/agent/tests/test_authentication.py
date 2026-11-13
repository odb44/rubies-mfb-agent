"""Authentication boundary tests for the agent application."""

from unittest.mock import AsyncMock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from rubies_agent.app import require_authenticated_customer
from rubies_agent.clients.banking_api_client import BankingAPIError


def create_protected_test_app() -> FastAPI:
    """Create a minimal test route using the production auth dependency."""
    app = FastAPI()

    @app.get("/protected")
    def protected(
        identity=Depends(require_authenticated_customer),  # noqa: B008
    ) -> dict[str, str]:
        return {
            "customer_id": identity.customer_id,
            "session_id": identity.session_id,
        }

    return app


def test_request_without_token_is_rejected():
    """Requests without authentication must not reach protected resources."""
    with TestClient(create_protected_test_app()) as client:
        response = client.get("/protected")

    assert response.status_code == 401


def test_invalid_bearer_token_is_rejected():
    """An invalid bearer token must not authenticate a customer."""
    with patch("rubies_agent.app.BankingAPIClient") as client_factory:
        client_factory.return_value.validate_session = AsyncMock(
            side_effect=BankingAPIError("Authentication is required or the session has expired.")
        )
        with TestClient(create_protected_test_app()) as client:
            response = client.get(
                "/protected",
                headers={"Authorization": "Bearer invalid-token"},
            )

    assert response.status_code == 401
