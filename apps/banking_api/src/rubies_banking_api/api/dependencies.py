"""Shared FastAPI dependencies for authenticated banking operations."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from rubies_security.authentication import (
    AuthenticationError,
    TokenSettings,
    authenticate_access_token,
)
from rubies_security.identity import IdentityVerificationError
from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_customer_identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> CustomerIdentity:
    """Authenticate a bearer token and return its trusted customer identity."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated customer identity is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()

    try:
        settings.validate_jwt_configuration()

        token_settings = TokenSettings(
            secret_key=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )

        return authenticate_access_token(
            credentials.credentials,
            token_settings,
        )

    except (AuthenticationError, ValueError, IdentityVerificationError) as exc:
        print(
            f"[AUTH DEBUG] Validation failed: {type(exc).__name__}: {exc}",
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token is invalid or customer verification is required.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
