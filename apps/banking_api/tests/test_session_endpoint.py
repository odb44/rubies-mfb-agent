from types import SimpleNamespace

from fastapi.testclient import TestClient
from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.main import app


def test_session_endpoint_returns_trusted_identity():
    app.dependency_overrides[get_customer_identity] = lambda: SimpleNamespace(
        customer_id="customer-001", session_id="session-001"
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/auth/session", headers={"Authorization": "Bearer test"})
        assert response.status_code == 200
        assert response.json() == {"customer_id": "customer-001", "session_id": "session-001"}
    finally:
        app.dependency_overrides.pop(get_customer_identity, None)


def test_session_endpoint_requires_authentication():
    app.dependency_overrides.pop(get_customer_identity, None)
    with TestClient(app) as client:
        response = client.get("/api/auth/session")
    assert response.status_code == 401
