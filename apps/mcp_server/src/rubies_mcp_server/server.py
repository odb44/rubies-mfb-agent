"""Authenticated and instrumented MCP server for Rubies MFB banking operations."""

import logging
import os
from time import perf_counter
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

import re
from uuid import uuid4
from collections.abc import Awaitable, Callable


from rubies_observability import (
    configure_logging,
    get_correlation_id,
    log_event,
    correlation_context,
)
from rubies_security.authentication import (
    AuthenticationError,
    TokenSettings,
    authenticate_access_token,
)
from rubies_security.identity import IdentityVerificationError
from rubies_loan_model.inference import LoanModelInference
from rubies_loan_model.schemas import LoanApplicantInput

from rubies_mcp_server.banking_client import (
    BankingAPIClient,
    BankingAPIError,
)


LOGGER = logging.getLogger("rubies.mcp_server")

LOAN_APPLICANT_FIELDS = {
    "Gender",
    "Married",
    "Dependents",
    "Education",
    "Self_Employed",
    "ApplicantIncome",
    "CoapplicantIncome",
    "LoanAmount",
    "Loan_Amount_Term",
    "Credit_History",
    "Property_Area",
}

ALLOWED_SUPPORT_ROUTES = {
    "PAYMENTS_OPERATIONS",
    "CARD_SUPPORT",
    "FRAUD_AND_SECURITY",
    "CUSTOMER_EXPERIENCE",
    "ACCOUNT_SERVICES",
    "LENDING_OPERATIONS",
    "GENERAL_HUMAN_SUPPORT",
}

ALLOWED_SUPPORT_PRIORITIES = {"P1", "P2", "P3", "P4"}


def _record_event(
    *,
    event: str,
    outcome: str,
    duration_ms: float | None = None,
    exception: Exception | None = None,
    **metadata: Any,
) -> None:
    """Write a structured event without allowing logging to break a tool."""

    safe_metadata = {
        key: value
        for key, value in metadata.items()
        if value is not None
    }

    try:
        log_event(
    LOGGER,
    component="mcp_server",
    event=event,
    outcome=outcome,
    duration_ms=duration_ms,
    exception_type=(
        type(exception).__name__
        if exception is not None
        else None
    ),
    metadata=safe_metadata,
)
    except Exception:
        # Observability failures must not change banking-tool behaviour.
        LOGGER.warning(
            "Structured observability event could not be recorded.",
            exc_info=True,
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
    """Build MCP authentication metadata settings."""

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


class RubiesTokenVerifier(TokenVerifier):
    """Validate bearer tokens using the shared Rubies security package."""

    def __init__(self, settings: TokenSettings) -> None:
        self._settings = settings

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an authenticated MCP token or None when invalid."""

        try:
            identity = authenticate_access_token(
                token,
                self._settings,
            )
        except (AuthenticationError, IdentityVerificationError):
            _record_event(
                event="mcp_token_validation",
                outcome="failure",
                reason="invalid_or_unverified_token",
            )
            return None

        if not identity.verified:
            _record_event(
                event="mcp_token_validation",
                outcome="failure",
                reason="identity_not_verified",
            )
            return None

        _record_event(
            event="mcp_token_validation",
            outcome="success",
        )

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


def get_trusted_identity(
    settings: TokenSettings,
) -> tuple[str, str]:
    """Resolve the trusted customer and session from the MCP request."""

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
    except IdentityVerificationError as exc:
        raise PermissionError(
            "Customer verification is required."
        ) from exc

    if not identity.verified:
        raise PermissionError("Customer verification is required.")

    if access_token.client_id != identity.customer_id:
        raise PermissionError("Authenticated identity mismatch.")

    return identity.customer_id, identity.session_id


def _check_tool_access(
    tool_name: str,
    settings: TokenSettings,
) -> tuple[str, str]:
    """Authenticate the caller and restrict access to registered tools."""

    allowed_tools = {
        "verify_customer",
        "get_customer_accounts",
        "get_balance",
        "get_mini_statement",
        "get_transaction_status",
        "open_dispute",
        "block_card",
        "create_confirmation",
        "approve_confirmation",
        "check_loan_eligibility",
        "get_loan_status",
        "handoff_to_human",
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


def _tool_started() -> float:
    """Return a monotonic timestamp for tool-duration measurements."""

    return perf_counter()


def _tool_succeeded(
    tool_name: str,
    started_at: float,
) -> None:
    """Record a successful tool execution."""

    _record_event(
        event="mcp_tool_execution",
        outcome="success",
        tool_name=tool_name,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


def _tool_failed(
    tool_name: str,
    started_at: float,
    exception: Exception,
) -> None:
    """Record a failed tool execution without sensitive input values."""

    _record_event(
        event="mcp_tool_execution",
        outcome="failure",
        tool_name=tool_name,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        exception=exception,
    )

CORRELATION_HEADER = b"x-correlation-id"
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class CorrelationIdMiddleware:
    """Propagate a validated correlation ID through MCP HTTP requests."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        incoming_id = headers.get(CORRELATION_HEADER, b"")
        correlation_id = incoming_id.decode("ascii", errors="ignore").strip()

        if not CORRELATION_ID_PATTERN.fullmatch(correlation_id):
            correlation_id = str(uuid4())

        async def send_with_correlation_id(message) -> None:
            if message["type"] == "http.response.start":
                response_headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != CORRELATION_HEADER
                ]
                response_headers.append(
                    (
                        CORRELATION_HEADER,
                        correlation_id.encode("ascii"),
                    )
                )
                message = {
                    **message,
                    "headers": response_headers,
                }

            await send(message)

        with correlation_context(correlation_id):
            await self.app(scope, receive, send_with_correlation_id)    


def create_server(
    client: BankingAPIClient,
    token_settings: TokenSettings | None = None,
    auth_settings: AuthSettings | None = None,
) -> FastMCP:
    """Create the authenticated MCP server and register banking tools."""

    settings = token_settings or _token_settings_from_environment()
    mcp_auth_settings = (
        auth_settings or _auth_settings_from_environment()
    )

    server = FastMCP(
        name="Rubies MFB Banking Tools",
        token_verifier=RubiesTokenVerifier(settings),
        auth=mcp_auth_settings,
        host=os.environ.get("MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCP_PORT", "8002")),
        stateless_http=True,
    )

    @server.tool()
    async def verify_customer() -> dict[str, Any]:
        """Confirm that the current request has a verified trusted identity."""
        started_at = _tool_started()
        try:
            customer_id, _session_id = _check_tool_access("verify_customer", settings)
            _tool_succeeded("verify_customer", started_at)
            return {"success": True, "verified": True, "customer_reference": customer_id}
        except Exception as exc:
            _tool_failed("verify_customer", started_at, exc)
            raise


    @server.tool()
    async def get_customer_accounts() -> dict[str, Any]:
        """Retrieve active accounts belonging to the authenticated customer."""
        started_at = _tool_started()
        try:
            _check_tool_access("get_customer_accounts", settings)

            result = await client.get_customer_accounts(
                access_token=_get_request_token(),
            )

            _tool_succeeded("get_customer_accounts", started_at)
            return result

        except Exception as exc:
            _tool_failed("get_customer_accounts", started_at, exc)
            raise    

    @server.tool()
    async def get_balance(account_reference: str) -> dict[str, Any]:
        """Retrieve the balance of an account owned by the authenticated customer."""
        started_at = _tool_started()
        try:
            _check_tool_access("get_balance", settings)
            result = await client.get_balance(account_reference, access_token=_get_request_token())
            _tool_succeeded("get_balance", started_at)
            return result
        except Exception as exc:
            _tool_failed("get_balance", started_at, exc)
            raise

    @server.tool()
    async def get_mini_statement(account_reference: str, limit: int = 10, offset: int = 0) -> dict[str, Any]:
        """Retrieve a bounded mini-statement for the authenticated customer's account."""
        started_at = _tool_started()
        try:
            _check_tool_access("get_mini_statement", settings)
            if not 1 <= limit <= 50 or offset < 0:
                return {"success": False, "status": "INVALID_INPUT", "message": "Limit must be 1-50 and offset cannot be negative."}
            result = await client.get_mini_statement(account_reference, limit=limit, offset=offset, access_token=_get_request_token())
            _tool_succeeded("get_mini_statement", started_at)
            return result
        except Exception as exc:
            _tool_failed("get_mini_statement", started_at, exc)
            raise

    @server.tool()
    async def open_dispute(confirmation_id: str, category: str, description: str, transaction_reference: str | None = None) -> dict[str, Any]:
        """Submit a dispute only with a server-approved, action-bound confirmation ID."""
        started_at = _tool_started()
        try:
            _check_tool_access("open_dispute", settings)
            if not confirmation_id.strip() or not category.strip() or not description.strip():
                return {"success": False, "status": "INVALID_INPUT", "message": "Confirmation, category, and description are required."}
            result = await client.open_dispute(confirmation_id=confirmation_id, category=category, description=description, transaction_reference=transaction_reference, access_token=_get_request_token())
            _tool_succeeded("open_dispute", started_at)
            return result
        except Exception as exc:
            _tool_failed("open_dispute", started_at, exc)
            raise

    @server.tool()
    async def block_card(card_reference: str, confirmation_id: str) -> dict[str, Any]:
        """Block a card only with a server-approved, action-bound confirmation ID."""
        started_at = _tool_started()
        try:
            _check_tool_access("block_card", settings)
            if not card_reference.strip() or not confirmation_id.strip():
                return {"success": False, "status": "INVALID_INPUT", "message": "Card reference and confirmation ID are required."}
            result = await client.block_card(card_reference=card_reference, confirmation_id=confirmation_id, access_token=_get_request_token())
            _tool_succeeded("block_card", started_at)
            return result
        except Exception as exc:
            _tool_failed("block_card", started_at, exc)
            raise
    
    @server.tool()
    async def create_confirmation(
        action: str,
        payload: dict[str, str],
    ) -> dict[str, Any]:
        """Create a pending confirmation for a sensitive banking action."""
        started_at = _tool_started()
        try:
            _check_tool_access("create_confirmation", settings)

            result = await client.create_confirmation(
                action=action,
                payload=payload,
                access_token=_get_request_token(),
            )

            _tool_succeeded("create_confirmation", started_at)
            return result
        except Exception as exc:
            _tool_failed("create_confirmation", started_at, exc)
            raise

    @server.tool()
    async def approve_confirmation(
        confirmation_id: str,
        action: str,
        payload: dict[str, str],
    ) -> dict[str, Any]:
        """Approve a confirmation after the customer explicitly agrees."""
        started_at = _tool_started()
        try:
            _check_tool_access("approve_confirmation", settings)

            if not confirmation_id.strip():
                return {
                    "success": False,
                    "status": "INVALID_INPUT",
                    "message": "Confirmation ID is required.",
                }

            result = await client.approve_confirmation(
                confirmation_id=confirmation_id,
                action=action,
                payload=payload,
                access_token=_get_request_token(),
            )

            _tool_succeeded("approve_confirmation", started_at)
            return result
        except Exception as exc:
            _tool_failed("approve_confirmation", started_at, exc)
            raise

    @server.tool()
    async def get_transaction_status(
        transaction_reference: str,
    ) -> dict[str, Any]:
        """Retrieve a transaction status for the authenticated customer."""

        started_at = _tool_started()

        try:
            _check_tool_access("get_transaction_status", settings)

            result = await client.get_transaction_status(
                transaction_reference,
                access_token=_get_request_token(),
            )

            _tool_succeeded("get_transaction_status", started_at)
            return result

        except Exception as exc:
            _tool_failed(
                "get_transaction_status",
                started_at,
                exc,
            )
            raise

    @server.tool()
    async def get_loan_status(
        loan_reference: str,
    ) -> dict[str, Any]:
        """Retrieve a loan status for the authenticated customer."""

        started_at = _tool_started()

        try:
            _check_tool_access("get_loan_status", settings)

            result = await client.get_loan_status(
                loan_reference,
                access_token=_get_request_token(),
            )

            _tool_succeeded("get_loan_status", started_at)
            return result

        except Exception as exc:
            _tool_failed(
                "get_loan_status",
                started_at,
                exc,
            )
            raise


    @server.tool()
    async def check_loan_eligibility() -> dict[str, Any]:
        """Check preliminary eligibility using existing authenticated
        customer data and approved lending criteria.

        This tool must not use the historical demonstration model to make
        an actual lending decision.
        """
        started_at = _tool_started()

        try:
            _check_tool_access("check_loan_eligibility", settings)

            # No customer ID or applicant data is accepted from the model.
            # The downstream service must derive customer identity from
            # the trusted authenticated request context.
            result = await client.check_loan_eligibility(
                access_token=_get_request_token(),
            )

            if not isinstance(result, dict):
                result = {
                    "success": False,
                    "status": "INVALID_RESPONSE",
                    "message": (
                        "The eligibility service returned an invalid response."
                    ),
                }

            # Fail closed: never treat a historical-model estimate as a
            # genuine bank eligibility decision.
            if result.get("status") == "MODEL_ESTIMATE":
                result = {
                    "success": False,
                    "status": "ASSESSMENT_UNAVAILABLE",
                    "message": (
                        "The historical demonstration model cannot determine "
                        "actual Rubies MFB loan eligibility."
                    ),
                }

            _tool_succeeded("check_loan_eligibility", started_at)
            return result

        except Exception as exc:
            _tool_failed(
                "check_loan_eligibility",
                started_at,
                exc,
            )
            raise


    @server.tool()
    async def handoff_to_human(
        reason: str,
        summary: str,
        route: str,
        priority: str,
        actions_attempted: list[str],
        unresolved_questions: list[str],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Queue a customer support request for human follow-up.

        A successful response confirms that the request was queued.
        It does not mean that a human has acknowledged it.
        """

        started_at = _tool_started()

        try:
            _check_tool_access("handoff_to_human", settings)

            if route not in ALLOWED_SUPPORT_ROUTES:
                result = {
                    "success": False,
                    "status": "HANDOFF_FAILED",
                    "message": "The specified support route is invalid.",
                }
                _tool_succeeded("handoff_to_human", started_at)
                return result

            if priority not in ALLOWED_SUPPORT_PRIORITIES:
                result = {
                    "success": False,
                    "status": "HANDOFF_FAILED",
                    "message": (
                        "The specified support priority is invalid."
                    ),
                }
                _tool_succeeded("handoff_to_human", started_at)
                return result

            if not reason.strip() or not summary.strip():
                result = {
                    "success": False,
                    "status": "HANDOFF_FAILED",
                    "message": "A reason and summary are required.",
                }
                _tool_succeeded("handoff_to_human", started_at)
                return result

            result = await client.create_support_handoff(
                reason=reason,
                summary=summary,
                route=route,
                priority=priority,
                actions_attempted=actions_attempted,
                unresolved_questions=unresolved_questions,
                correlation_id=correlation_id,
                access_token=_get_request_token(),
            )

        except BankingAPIError as exc:
            _tool_failed(
                "handoff_to_human",
                started_at,
                exc,
            )
            return {
                "success": False,
                "status": "HANDOFF_FAILED",
                "message": (
                    "The support request could not be confirmed as "
                    "queued. Do not tell the customer that a human "
                    "has been notified."
                ),
            }

        except Exception as exc:
            _tool_failed(
                "handoff_to_human",
                started_at,
                exc,
            )
            raise

        if not isinstance(result, dict):
            _record_event(
                event="mcp_handoff_response_validation",
                outcome="failure",
                reason="response_not_object",
            )
            _tool_failed(
                "handoff_to_human",
                started_at,
                ValueError("Invalid support API response."),
            )
            return {
                "success": False,
                "status": "HANDOFF_FAILED",
                "message": (
                    "The support API returned an invalid response. "
                    "Do not tell the customer that a human has "
                    "been notified."
                ),
            }

        data = result.get("data", result)

        if not isinstance(data, dict):
            _tool_failed(
                "handoff_to_human",
                started_at,
                ValueError("Invalid support API response data."),
            )
            return {
                "success": False,
                "status": "HANDOFF_FAILED",
                "message": (
                    "The support API returned an invalid response. "
                    "Do not tell the customer that a human has "
                    "been notified."
                ),
            }

        reference = data.get("reference")
        handoff_status = data.get("status")

        if not reference or not handoff_status:
            _tool_failed(
                "handoff_to_human",
                started_at,
                ValueError("Support handoff confirmation is incomplete."),
            )
            return {
                "success": False,
                "status": "HANDOFF_FAILED",
                "message": (
                    "The support request could not be confirmed as "
                    "queued. Do not tell the customer that a human "
                    "has been notified."
                ),
            }

        _tool_succeeded("handoff_to_human", started_at)

        return {
            "success": True,
            "data": {
                "reference": reference,
                "status": handoff_status,
                "priority": data.get("priority", priority),
                "route": data.get("route", route),
                "acknowledged_at": data.get("acknowledged_at"),
                "acknowledgement_reference": data.get(
                    "acknowledgement_reference"
                ),
            },
            "message": (
                "The support request has been queued and is awaiting "
                "human acknowledgement. Do not claim that a human "
                "has acknowledged the request."
            ),
        }

    _record_event(
        event="mcp_server_created",
        outcome="success",
        registered_tool_count=12,
    )

    return server


def main() -> None:
    """Start the MCP server over Streamable HTTP."""

    configure_logging()

    settings = _token_settings_from_environment()

    banking_api_url = os.environ.get(
        "BANKING_API_BASE_URL",
        "http://127.0.0.1:8000",
    ).strip()

    if not banking_api_url:
        raise RuntimeError(
            "BANKING_API_BASE_URL must not be empty."
        )

    client = BankingAPIClient(base_url=banking_api_url)
    server = create_server(client, settings)

    _record_event(
        event="mcp_server_starting",
        outcome="success",
        transport="streamable-http",
    )

    import uvicorn

    app = server.streamable_http_app()
    app.add_middleware(CorrelationIdMiddleware)
    uvicorn.run(
            app,
            host=server.settings.host,
            port=server.settings.port,
            log_level=server.settings.log_level.lower(),
)


if __name__ == "__main__":
    main()