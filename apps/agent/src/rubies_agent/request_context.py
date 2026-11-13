"""Request-scoped authentication context for Banking API calls."""

from contextvars import ContextVar
from typing import Any

_request_access_token: ContextVar[str | None] = ContextVar(
    "rubies_agent_request_access_token",
    default=None,
)


def set_request_access_token(token: str):
    """Set the authenticated token for the current request context."""
    return _request_access_token.set(token)


def reset_request_access_token(token_context: Any) -> None:
    """Restore the previous token context after the request finishes."""
    _request_access_token.reset(token_context)


def get_request_access_token() -> str:
    """Return the current request's trusted bearer token."""
    token = _request_access_token.get()

    if token is None or not token.strip():
        raise RuntimeError("An authenticated customer access token is required.")

    return token.strip()


def _get_request_access_token() -> str:
    """Backward-compatible internal accessor for the current request token."""
    return get_request_access_token()
