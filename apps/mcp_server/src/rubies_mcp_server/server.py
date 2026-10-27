"""Authenticated MCP server for Rubies MFB banking operations."""

import os
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from rubies_mcp_server.banking_client import BankingAPIClient, BankingAPIError
from rubies_security.authentication import (
    AuthenticationError,
    TokenSettings,
    authenticate_access_token,
)


class RubiesTokenVerifier(TokenVerifier):
    """Validate bearer tokens using the shared Rubies security package."""

    def __init__(self, settings: TokenSettings) -> None:
        self._settings = settings

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an authenticated MCP token, or None when validation fails."""
        try:
            identity = authenticate_access_token(token, self._settings)
        except AuthenticationError:
            return None

        if not identity.verified:
            return None

        return AccessToken(
            token=token,
            client_id=identity.customer_id,
            subject=identity.customer_id,
            scopes=[],
            claims={
                "customer_id": identity.customer_id,
                "session_id": identity.session_id,
                "verified": identity.verified,
            },
        )


def _token_settings_from_environment() -> TokenSettings:
    """Build JWT validation settings from environment variables."""
    required_variables = (
        "JWT_SECRET_KEY",
        "JWT_ISSUER",
        "JWT_AUDIENCE",
    )

    missing = [
        name
        for name in required_variables
        if not os.environ.get(name, "").strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing required authentication environment variables: "
            + ", ".join(missing)
        )

    return TokenSettings(
        secret_key=os.environ["JWT_SECRET_KEY"],
        issuer=os.environ["JWT_ISSUER"],
        audience=os.environ["JWT_AUDIENCE"],
    )


def _auth_settings_from_environment() -> AuthSettings:
    """Build MCP authentication metadata settings from environment variables.

    These URLs describe the MCP resource server. They do not configure a
    separate OAuth authorization server or replace the custom JWT verifier.
    """
    issuer_url = os.environ.get(
        "MCP_AUTH_ISSUER_URL",
        "http://127.0.0.1:8000",
    ).strip()

    resource_server_url = os.environ.get(
        "MCP_RESOURCE_SERVER_URL",
        "http://127.0.0.1:8000",
    ).strip()

    if not issuer_url or not resource_server_url:
        raise RuntimeError(
            "MCP_AUTH_ISSUER_URL and MCP_RESOURCE_SERVER_URL "
            "must not be empty."
        )

    return AuthSettings(
        issuer_url=issuer_url,
        resource_server_url=resource_server_url,
        validate_token_resource=False,
    )


def get_trusted_identity(
    settings: TokenSettings,
) -> tuple[str, str]:
    """Resolve the authenticated customer and session from the request context.

    Returns:
        A tuple containing the trusted customer ID and session ID.

    Raises:
        PermissionError: If the request has no valid, verified identity.
    """
    access_token = get_access_token()

    if access_token is None:
        raise PermissionError("Authentication is required.")

    try:
        identity = authenticate_access_token(
            access_token.token,
            settings,
        )
    except AuthenticationError as exc:
        raise PermissionError(
            "The access token is invalid or expired."
        ) from exc

    if not identity.verified:
        raise PermissionError("Customer verification is required.")

    # The identity derived from the token must match the authenticated
    # client identity supplied by the MCP authentication context.
    if access_token.client_id != identity.customer_id:
        raise PermissionError("Authenticated identity mismatch.")

    return identity.customer_id, identity.session_id


def _check_tool_access(
    tool_name: str,
    settings: TokenSettings,
) -> tuple[str, str]:
    """Authenticate the caller and restrict access to registered tools."""
    allowed_tools = {
        "get_transaction_status",
        "get_loan_status",
    }

    if tool_name not in allowed_tools:
        raise PermissionError("This tool is not available.")

    return get_trusted_identity(settings)


def _get_request_token() -> str:
    """Retrieve the bearer token from the authenticated MCP request."""
    access_token = get_access_token()

    if access_token is None:
        raise PermissionError("Authentication is required.")

    return access_token.token


def create_server(
    client: BankingAPIClient,
    token_settings: TokenSettings | None = None,
    auth_settings: AuthSettings | None = None,
) -> FastMCP:
    """Create the authenticated MCP server and register banking tools."""
    settings = token_settings or _token_settings_from_environment()
    mcp_auth_settings = auth_settings or _auth_settings_from_environment()

    server = FastMCP(
        name="Rubies MFB Banking Tools",
        token_verifier=RubiesTokenVerifier(settings),
        auth=mcp_auth_settings,
        stateless_http=True,
    )

    @server.tool()
    async def get_transaction_status(
        transaction_reference: str,
    ) -> dict[str, Any]:
        """Retrieve the status of a transaction belonging to the authenticated customer.

        Args:
            transaction_reference: The transaction reference to look up.

        Returns:
            The transaction status returned by the Banking API.
        """
        _check_tool_access("get_transaction_status", settings)

        return await client.get_transaction_status(
            transaction_reference,
            access_token=_get_request_token(),
        )

    @server.tool()
    async def get_loan_status(
        loan_reference: str,
    ) -> dict[str, Any]:
        """Retrieve the status of a loan belonging to the authenticated customer.

        Args:
            loan_reference: The loan reference to look up.

        Returns:
            The loan status returned by the Banking API.
        """
        _check_tool_access("get_loan_status", settings)

        return await client.get_loan_status(
            loan_reference,
            access_token=_get_request_token(),
        )

    return server


def main() -> None:
    """Start the MCP server over Streamable HTTP."""
    settings = _token_settings_from_environment()

    banking_api_url = os.environ.get(
        "BANKING_API_BASE_URL",
        "http://127.0.0.1:8000",
    ).strip()

    if not banking_api_url:
        raise RuntimeError("BANKING_API_BASE_URL must not be empty.")

    client = BankingAPIClient(base_url=banking_api_url)
    server = create_server(client, settings)

    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
