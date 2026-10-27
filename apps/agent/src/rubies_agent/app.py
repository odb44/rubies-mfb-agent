"""FastAPI application for the Rubies MFB support agent."""

from collections.abc import AsyncIterator
from typing import Any

from ag_ui.core import RunAgentInput
from ag_ui_strands import StrandsAgent, add_strands_fastapi_endpoint
from fastapi import Depends, FastAPI, HTTPException, Request
from rubies_banking_api.api.dependencies import get_customer_identity
from strands import Agent

from rubies_agent.runtime import (
    build_agent,
    reset_request_access_token,
    set_request_access_token,
)


async def require_authenticated_customer(
    request: Request,
    identity=Depends(get_customer_identity),  # noqa: B008
) -> AsyncIterator[Any]:
    """Authenticate the customer and scope their token to this request."""

    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")

    if (
        not separator
        or scheme.lower() != "bearer"
        or not token.strip()
    ):
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
        raise RuntimeError(
            "Authenticated customer context is missing."
        )

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
