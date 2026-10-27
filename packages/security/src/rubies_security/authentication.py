"""JWT authentication and trusted identity construction."""

from dataclasses import dataclass
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from rubies_shared import CustomerIdentity

from rubies_security.identity import IdentityVerificationError


class AuthenticationError(Exception):
    """Raised when access-token authentication fails."""


@dataclass(frozen=True, slots=True)
class TokenSettings:
    """Configuration required to validate access tokens."""

    secret_key: str
    issuer: str
    audience: str
    algorithm: str = "HS256"

    def __post_init__(self) -> None:
        if len(self.secret_key) < 32:
            raise ValueError("JWT secret must contain at least 32 characters.")
        if not self.issuer.strip():
            raise ValueError("JWT issuer must not be empty.")
        if not self.audience.strip():
            raise ValueError("JWT audience must not be empty.")
        if self.algorithm != "HS256":
            raise ValueError("Only the configured HS256 algorithm is supported.")


def authenticate_access_token(
    token: str,
    settings: TokenSettings,
) -> CustomerIdentity:
    """Validate an access token and construct its trusted customer identity."""

    if not token or not token.strip():
        raise AuthenticationError("An access token is required.")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            issuer=settings.issuer,
            audience=settings.audience,
            options={
                "require": ["exp", "iat", "sub", "sid", "iss", "aud"],
            },
        )
    except InvalidTokenError as exc:
        raise AuthenticationError("The access token is invalid or expired.") from exc

    customer_id = claims.get("sub")
    session_id = claims.get("sid")
    verified = claims.get("verified")

    if (
        not isinstance(customer_id, str)
        or not customer_id.strip()
        or not isinstance(session_id, str)
        or not session_id.strip()
        or not isinstance(verified, bool)
    ):
        raise AuthenticationError("The access token contains invalid identity claims.")

    if not verified:
        raise IdentityVerificationError("Customer verification is required.")

    return CustomerIdentity(
        customer_id=customer_id,
        session_id=session_id,
        verified=verified,
    )