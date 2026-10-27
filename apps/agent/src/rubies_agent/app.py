"""FastAPI application for the Rubies MFB support agent."""

import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from ag_ui.core import RunAgentInput
from ag_ui_strands import StrandsAgent, add_strands_fastapi_endpoint
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_observability import (
    configure_logging,
    correlation_context,
    log_event,
)
from strands import Agent

from rubies_agent.runtime import (
    build_agent,
    reset_request_access_token,
    set_request_access_token,
)

CORRELATION_HEADER = "X-Correlation-ID"
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

configure_logging()
logger = logging.getLogger("rubies.agent")


def resolve_correlation_id(request: Request) -> str:
    """Use a valid incoming correlation ID or generate a new one."""

    incoming_id = request.headers.get(CORRELATION_HEADER, "").strip()

    if CORRELATION_ID_PATTERN.fullmatch(incoming_id):
        return incoming_id

    return str(uuid4())


async def require_authenticated_customer(
    request: Request,
    identity=Depends(get_customer_identity),  # noqa: B008
) -> AsyncIterator[Any]:
    """Authenticate the customer and scope their token to this request."""

    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required.",
        )

    request.state.customer_identity = identity
    token_context = set_request_access_token(token.strip())

    try:
        yield identity
    finally:
        reset_request_access_token(token_context)


async def build_invocation_state(
    request: Request,
    input_data: RunAgentInput,
) -> dict[str, Any]:
    """Build trusted server-side context for an agent invocation."""

    identity = getattr(request.state, "customer_identity", None)

    if identity is None:
        raise RuntimeError("Authenticated customer context is missing.")

    return {
        "customer_id": identity.customer_id,
        "session_id": identity.session_id,
        "run_id": input_data.run_id,
    }


def create_app(agent: Agent | None = None) -> FastAPI:
    """Create the application with a configured or injected agent."""

    agent_template = agent if agent is not None else build_agent()

    agui_agent = StrandsAgent(
        agent=agent_template,
        name="rubies_mfb_support",
    )

    app = FastAPI(
        title="Rubies MFB Customer Support Agent",
        version="0.1.0",
    )


    @app.middleware("http")
    async def correlation_middleware(
        request: Request,
        call_next,
    ) -> Response:
        """Attach a correlation ID to the request and its log events."""

        correlation_id = resolve_correlation_id(request)
        request.state.correlation_id = correlation_id
        started_at = time.perf_counter()

        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")

        try:
            with correlation_context(correlation_id):
                response = await call_next(request)

                duration_ms = round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                )

                response.headers[CORRELATION_HEADER] = correlation_id

                try:
                    log_event(
                        logger,
                        "http_request",
                        component="agent",
                        outcome=(
                            "success"
                            if response.status_code < 500
                            else "failure"
                        ),
                        duration_ms=duration_ms,
                        metadata={
                            "method": request.method,
                            "route": route_path,
                            "status_code": response.status_code,
                        },
                    )
                except Exception:
                    logger.exception(
                        "Failed to record agent HTTP request."
                    )

                return response

        except Exception as exc:
            try:
                with correlation_context(correlation_id):
                    log_event(
                        logger,
                        "http_request",
                        component="agent",
                        outcome="failure",
                        duration_ms=round(
                            (time.perf_counter() - started_at) * 1000,
                            2,
                        ),
                        exception_type=type(exc).__name__,
                        metadata={
                            "method": request.method,
                            "route": route_path,
                            "status_code": 500,
                        },
                    )
            except Exception:
                logger.exception(
                    "Failed to record agent HTTP request failure."
                )

            raise


    add_strands_fastapi_endpoint(
        app,
        agui_agent,
        "/api/agent",
        auth=require_authenticated_customer,
        invocation_state_provider=build_invocation_state,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Report application health without invoking the model."""
        return {"status": "ok"}

    return app