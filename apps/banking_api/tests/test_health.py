from fastapi.testclient import TestClient
from rubies_banking_api.main import app

client = TestClient(app)


def test_root_endpoint_returns_service_information() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Rubies MFB Banking API",
        "message": "Welcome to the Rubies MFB Banking API.",
        "health": "/health",
        "documentation": "/docs",
    }


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "banking-api",
        "environment": "development",
    }