from datetime import UTC, datetime, timedelta

import jwt
import pytest
from rubies_security.authentication import (
    AuthenticationError,
    TokenSettings,
    authenticate_access_token,
)
from rubies_security.identity import IdentityVerificationError

SECRET = "test-secret-key-that-is-at-least-32-characters-long"
ISSUER = "rubies-mfb-test"
AUDIENCE = "rubies-mfb-api"


@pytest.fixture
def settings() -> TokenSettings:
    return TokenSettings(
        secret_key=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
    )


def make_token(
    *,
    verified: bool = True,
    secret: str = SECRET,
    expires_in: timedelta = timedelta(minutes=5),
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": "CUS-0007",
            "sid": "session-test-001",
            "verified": verified,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + expires_in,
        },
        secret,
        algorithm="HS256",
    )


def test_authenticates_valid_token(settings: TokenSettings) -> None:
    identity = authenticate_access_token(make_token(), settings)

    assert identity.customer_id == "CUS-0007"
    assert identity.session_id == "session-test-001"
    assert identity.verified is True


def test_rejects_invalid_signature(settings: TokenSettings) -> None:
    token = make_token(secret="a-different-secret-that-is-also-at-least-32-chars")

    with pytest.raises(AuthenticationError):
        authenticate_access_token(token, settings)


def test_rejects_expired_token(settings: TokenSettings) -> None:
    token = make_token(expires_in=timedelta(seconds=-10))

    with pytest.raises(AuthenticationError):
        authenticate_access_token(token, settings)


def test_rejects_unverified_customer(settings: TokenSettings) -> None:
    token = make_token(verified=False)

    with pytest.raises(IdentityVerificationError):
        authenticate_access_token(token, settings)


def test_rejects_malformed_token(settings: TokenSettings) -> None:
    with pytest.raises(AuthenticationError):
        authenticate_access_token("not-a-jwt", settings)


def test_rejects_missing_session_claim(settings: TokenSettings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "CUS-0007",
            "verified": True,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        authenticate_access_token(token, settings)
        