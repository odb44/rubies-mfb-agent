"""FastAPI application for the Rubies MFB support agent."""

from typing import Any

from ag_ui.core import RunAgentInput
from ag_ui_strands import StrandsAgent, add_strands_fastapi_endpoint
from fastapi import Depends, FastAPI, Request
from rubies_banking_api.api.dependencies import get_customer_identity
from strands import Agent

from rubies_agent.runtime import build_agent


def require_authenticated_customer(
    request: Request,
    identity=Depends(get_customer_identity),  # noqa: B008
):
    """Authenticate the request and retain its trusted customer context."""
    request.state.customer_identity = identity
    return identity


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