"""Tests for the Rubies MFB agent application."""

from fastapi.testclient import TestClient
from rubies_agent.app import create_app
from strands import Agent


def test_health_endpoint_returns_ok():
    """The health endpoint should not require AWS credentials."""
    app = create_app(agent=Agent())

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
