"""HTTP-level tests for card endpoint authentication."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient
from rubies_banking_api.api import cards, dependencies
from rubies_banking_api.config import Settings
from rubies_banking_api.db.database import get_db
from rubies_banking_api.main import app

TEST_SECRET = "test-secret-key-that-is-at-least-32-characters-long"
TEST_ISSUER = "rubies-mfb"
TEST_AUDIENCE = "rubies-mfb-api"


class FakeSession:
    """Minimal database-session substitute for HTTP boundary tests."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture
def fake_db() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, fake_db: FakeSession):
    """Configure isolated dependencies for HTTP authentication tests."""

    test_settings = Settings(
        jwt_secret_key=TEST_SECRET,
        jwt_issuer=TEST_ISSUER,
        jwt_audience=TEST_AUDIENCE,
    )

    monkeypatch.setattr(
    dependencies,
    "get_settings",
    lambda: test_settings,
)
    app.dependency_overrides[get_db] = lambda: fake_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_token(
    *,
    verified: bool = True,
    secret: str = TEST_SECRET,
    expires_in: timedelta = timedelta(minutes=5),
) -> str:
    now = datetime.now(UTC)

    return jwt.encode(
        {
            "sub": "CUS-0007",
            "sid": "SESSION-TEST-001",
            "verified": verified,
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "iat": now,
            "exp": now + expires_in,
        },
        secret,
        algorithm="HS256",
    )


def test_block_card_rejects_missing_bearer_token(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/cards/CARD-TEST-001/block",
        json={"confirmation_id": "CONF-TEST-001"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_block_card_rejects_invalid_bearer_token(
    client: TestClient,
) -> None:
    token = make_token(
        secret="a-different-secret-that-is-also-at-least-32-chars"
    )

    response = client.post(
        "/api/cards/CARD-TEST-001/block",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmation_id": "CONF-TEST-001"},
    )

    assert response.status_code == 401


def test_block_card_rejects_unverified_customer(
    client: TestClient,
) -> None:
    token = make_token(verified=False)

    response = client.post(
        "/api/cards/CARD-TEST-001/block",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmation_id": "CONF-TEST-001"},
    )

    assert response.status_code == 401


def test_valid_token_reaches_card_service(
    client: TestClient,
    fake_db: FakeSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received = {}

    class FakeCardService:
        def __init__(self, **kwargs) -> None:
            received["repositories"] = kwargs

        def block_card(
            self,
            identity,
            *,
            card_reference: str,
            confirmation_id: str,
            correlation_id: str,
        ):
            received["identity"] = identity
            received["card_reference"] = card_reference
            received["confirmation_id"] = confirmation_id

            return SimpleNamespace(
                card_reference=card_reference,
                status="BLOCKED",
            )

    monkeypatch.setattr(cards, "CardService", FakeCardService)

    token = make_token()

    response = client.post(
        "/api/cards/CARD-TEST-001/block",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmation_id": "CONF-TEST-001"},
    )

    assert response.status_code == 200
    assert response.json()["card_reference"] == "CARD-TEST-001"
    assert response.json()["status"] == "BLOCKED"

    identity = received["identity"]
    assert identity.customer_id == "CUS-0007"
    assert identity.session_id == "SESSION-TEST-001"
    assert identity.verified is True

    assert received["confirmation_id"] == "CONF-TEST-001"
    assert fake_db.committed is True