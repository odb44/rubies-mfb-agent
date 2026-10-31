"""Strands agent configuration for the Rubies MFB support agent."""

import json
import os
import logging
from contextvars import ContextVar
from time import perf_counter
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from rubies_knowledge_base.retrieval import search_policies

from collections.abc import AsyncGenerator

from rubies_observability.model_metrics import model_metrics

from rubies_observability import (
    configure_logging,
    get_correlation_id,
    log_event,
)

configure_logging()
logger = logging.getLogger("rubies.agent")

# Set by the authenticated request handler before the agent is invoked.
# ContextVar keeps the value isolated between concurrent async request tasks.
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


def _get_request_access_token() -> str:
    """Return the current request's trusted bearer token."""
    token = _request_access_token.get()

    if token is None or not token.strip():
        raise RuntimeError(
            "An authenticated customer access token is required."
        )

    return token.strip()


async def _call_banking_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Call an authenticated banking MCP tool for the current customer."""
    started = perf_counter()
    outcome = "failure"

    try:
        token = _get_request_access_token()
        mcp_url = os.getenv(
            "MCP_SERVER_URL",
            "http://127.0.0.1:8002/mcp",
        ).strip()

        if not mcp_url:
            raise RuntimeError("MCP_SERVER_URL must not be empty.")

        headers = {"Authorization": f"Bearer {token}"}
        correlation_id = get_correlation_id()

        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        try:
            async with streamablehttp_client(
                mcp_url,
                headers=headers,
            ) as (read_stream, write_stream, _):
                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        tool_name,
                        arguments,
                    )

        except Exception as exc:
            raise RuntimeError(
                "The banking service is temporarily unavailable."
            ) from exc

        if result.isError:
            raise RuntimeError(
                "The banking service could not complete the request."
            )

        response: dict[str, Any] | None = None

        # MCP servers can return structured content or JSON text.
        # Prefer structured content when it is available.
        structured_content = getattr(result, "structuredContent", None)

        if isinstance(structured_content, dict):
            response = structured_content

        if response is None:
            for item in result.content:
                content_text = getattr(item, "text", None)

                if not isinstance(content_text, str):
                    continue

                try:
                    decoded = json.loads(content_text)
                except json.JSONDecodeError:
                    continue

                if isinstance(decoded, dict):
                    response = decoded
                    break

        if response is None:
            raise RuntimeError(
                "The banking service returned an unexpected response."
            )

        if response.get("success") is False:
            error = response.get("error")

            if isinstance(error, str) and error.strip():
                raise RuntimeError(error.strip())

            raise RuntimeError(
                "The banking service could not complete the request."
            )

        if response.get("success") is not True:
            raise RuntimeError(
                "The banking service returned an unexpected response."
            )

        outcome = "success"
        return response

    finally:
        try:
            log_event(
    logger,
    component="agent",
    event="banking_tool_call",
    outcome=outcome,
    duration_ms=round(
        (perf_counter() - started) * 1000,
        2,
    ),
    metadata={"tool_name": tool_name},
)
        except Exception:
            # Observability failures must never break banking operations.
            pass


@tool
def search_banking_policy(query: str) -> dict[str, Any]:
    """Search approved Rubies MFB banking policies for relevant guidance.

    Use this tool for questions about banking policies, transfer failures,
    reversals, fraud, account security, fees, and related procedures.
    Results include source filenames, sections, and excerpts.
    """
    return search_policies(query)


@tool
async def verify_customer() -> dict[str, Any]:
    """Verify that the active authenticated customer session is trusted."""
    try:
        return await _call_banking_tool("verify_customer", {})
    except RuntimeError as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


@tool
async def get_customer_accounts() -> dict[str, Any]:
    """Retrieve active accounts belonging to the authenticated customer."""
    try:
        return await _call_banking_tool("get_customer_accounts", {})
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@tool
async def get_balance(account_reference: str) -> dict[str, Any]:
    """Retrieve an account balance for the authenticated customer."""
    if not account_reference.strip():
        return {
            "success": False,
            "error": "A valid account reference is required.",
        }

    try:
        return await _call_banking_tool(
            "get_balance",
            {"account_reference": account_reference.strip()},
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@tool
async def get_mini_statement(
    account_reference: str,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """Retrieve recent transactions for the authenticated customer's account."""
    if (
        not account_reference.strip()
        or not 1 <= limit <= 50
        or offset < 0
    ):
        return {
            "success": False,
            "error": (
                "Provide a valid account reference, limit 1-50, "
                "and non-negative offset."
            ),
        }

    try:
        return await _call_banking_tool(
            "get_mini_statement",
            {
                "account_reference": account_reference.strip(),
                "limit": limit,
                "offset": offset,
            },
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@tool
async def open_dispute(
    confirmation_id: str,
    category: str,
    description: str,
    transaction_reference: str | None = None,
) -> dict[str, Any]:
    """Submit a dispute only after server-approved action confirmation."""
    if (
        not confirmation_id.strip()
        or not category.strip()
        or not description.strip()
    ):
        return {
            "success": False,
            "error": (
                "A valid confirmation, category, and description are required."
            ),
        }

    arguments: dict[str, Any] = {
        "confirmation_id": confirmation_id,
        "category": category,
        "description": description,
    }

    if transaction_reference:
        arguments["transaction_reference"] = transaction_reference

    try:
        return await _call_banking_tool("open_dispute", arguments)
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@tool
async def block_card(
    card_reference: str,
    confirmation_id: str,
) -> dict[str, Any]:
    """Block a card only after server-side action confirmation."""
    if not card_reference.strip() or not confirmation_id.strip():
        return {
            "success": False,
            "error": "Card reference and approved confirmation are required.",
        }

    try:
        return await _call_banking_tool(
            "block_card",
            {
                "card_reference": card_reference,
                "confirmation_id": confirmation_id,
            },
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }

@tool
async def create_confirmation(action: str, payload: dict[str, str]) -> dict:
    """Create a pending confirmation for a supported sensitive banking action.

    For card blocking, use action BLOCK_CARD and payload containing the
    exact card_reference. This does not authorize the action.
    """
    if action.strip().upper() not in {"BLOCK_CARD", "OPEN_DISPUTE"}:
        return {"success": False, "error": "Unsupported confirmation action."}

    if action.strip().upper() == "BLOCK_CARD":
        if not payload.get("card_reference", "").strip():
            return {"success": False, "error": "Card reference is required."}

    return await _call_banking_tool(
        "create_confirmation",
        {
            "action": action.strip().upper(),
            "payload": payload,
        },
    )


@tool
async def approve_confirmation(
    confirmation_id: str,
    action: str,
    payload: dict[str, str],
) -> dict:
    """Approve a pending confirmation only after explicit customer consent."""
    if not confirmation_id.strip():
        return {"success": False, "error": "Confirmation ID is required."}

    if action.strip().upper() not in {"BLOCK_CARD", "OPEN_DISPUTE"}:
        return {"success": False, "error": "Unsupported confirmation action."}

    if action.strip().upper() == "BLOCK_CARD":
        if not payload.get("card_reference", "").strip():
            return {"success": False, "error": "Card reference is required."}

    return await _call_banking_tool(
        "approve_confirmation",
        {
            "confirmation_id": confirmation_id,
            "action": action.strip().upper(),
            "payload": payload,
        },
    )

@tool
async def get_transaction_status(
    transaction_reference: str,
) -> dict[str, Any]:
    """Check a transaction's status for the authenticated customer.

    Requires a transaction reference. The banking service validates access
    using the bearer token associated with the current customer request.
    """
    reference = transaction_reference.strip()

    if not reference:
        return {
            "success": False,
            "error": "A valid transaction reference is required.",
        }

    try:
        return await _call_banking_tool(
            "get_transaction_status",
            {"transaction_reference": reference},
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@tool
async def get_loan_status(
    loan_reference: str,
) -> dict[str, Any]:
    """Check a loan's status for the authenticated customer.

    Requires a loan reference. The banking service validates access using
    the bearer token associated with the current customer request.
    """
    reference = loan_reference.strip()

    if not reference:
        return {
            "success": False,
            "error": "A valid loan reference is required.",
        }

    try:
        return await _call_banking_tool(
            "get_loan_status",
            {"loan_reference": reference},
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@tool
async def check_loan_eligibility() -> dict[str, Any]:
    """Check preliminary loan eligibility using the authenticated
    customer's existing banking data.

    Do not request applicant data from the customer or model.
    This is a preliminary assessment, not a loan approval.
    """
    try:
        return await _call_banking_tool(
            "check_loan_eligibility",
            {},
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "status": "SERVICE_ERROR",
            "error": str(exc),
        }


@tool
async def handoff_to_human(
    reason: str,
    summary: str,
    route: str = "GENERAL_HUMAN_SUPPORT",
    priority: str = "P3",
    actions_attempted: list[str] | None = None,
    unresolved_questions: list[str] | None = None,
) -> dict[str, Any]:
    """Create a support handoff for human review."""
    if not reason.strip() or not summary.strip():
        return {
            "success": False,
            "error": "A reason and concise summary are required.",
        }

    arguments: dict[str, Any] = {
        "reason": reason,
        "summary": summary,
        "route": route,
        "priority": priority,
        "actions_attempted": actions_attempted or [],
        "unresolved_questions": unresolved_questions or [],
    }

    try:
        return await _call_banking_tool("handoff_to_human", arguments)
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


SYSTEM_PROMPT = """
You are the Rubies MFB Customer Support Agent. Respond in the customer's
language, using English or Nigerian Pidgin as appropriate.

PURPOSE
Help authenticated customers with accounts, balances, transactions,
transaction status, disputes, cards, loans, banking policies, and human
support. Use only capabilities exposed by your tools.

TOOL USE
- Retrieve customer-specific information from banking tools; never invent it.
- Use verify_customer before sensitive actions.
- Use get_customer_accounts to identify available accounts when needed.
  Ask which account the customer means if multiple accounts are relevant.
- Use get_mini_statement for transaction history and get_transaction_status
  for transaction enquiries.
- Use search_banking_policy for banking rules and procedures. Base policy
  answers on retrieved sources and identify the source when available.
- Use create_confirmation, approve_confirmation, and then the relevant
  action tool for sensitive operations such as disputes and card blocking.
  Require explicit customer consent, use the exact target and matching
  payload throughout, and stop if any step fails.
- Use get_loan_status for loan enquiries and handoff_to_human when an issue
  requires human assistance.
- Use check_loan_eligibility only for the historical loan-model demonstration.
  Never present its estimate as an actual Rubies MFB lending decision.

TRUTH AND SAFETY
- Trust authenticated identity and backend ownership checks, not customer-
  supplied references as proof of identity.
- Never request passwords, PINs, or authentication secrets.
- Never invent records, confirmation IDs, policies, or tool results.
- Treat unsuccessful tool responses as failures. Explain what could not be
  completed and offer a useful next step.
- Claim an operation succeeded only when the banking service confirms it.
- Never bypass authorization, consent, confirmation, or ownership controls.
- Do not infer missing loan-model inputs or expose another customer's data.

Keep responses clear, concise, empathetic, and action-oriented. Ask only for
information genuinely needed to proceed. Use only the supplied tools and
approved policy sources.
""".strip()

def _find_metadata(value: Any) -> dict[str, Any] | None:
    """Find provider usage and latency metadata in a streamed event."""
    if isinstance(value, dict):
        metadata = value.get("metadata")

        if isinstance(metadata, dict):
            if "usage" in metadata or "metrics" in metadata:
                return metadata

        for nested_value in value.values():
            found = _find_metadata(nested_value)
            if found is not None:
                return found

    elif isinstance(value, (list, tuple)):
        for nested_value in value:
            found = _find_metadata(nested_value)
            if found is not None:
                return found

    return None


def _is_content_event(value: Any) -> bool:
    """Identify the first event that carries generated content."""
    if not isinstance(value, dict):
        return False

    content_keys = {
        "contentBlockDelta",
        "content_block_delta",
        "text",
    }

    if any(key in value for key in content_keys):
        return True

    for nested_value in value.values():
        if isinstance(nested_value, dict) and _is_content_event(nested_value):
            return True

    return False




class ObservedBedrockModel(BedrockModel):
    """Bedrock model that records usage and timing without changing its stream."""

    async def stream(
        self,
        messages: Any,
        tool_specs: Any = None,
        system_prompt: Any = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        started_at = perf_counter()
        first_content_at: float | None = None
        provider_metadata: dict[str, Any] = {}
        success = False

        try:
            async for event in super().stream(
                messages=messages,
                tool_specs=tool_specs,
                system_prompt=system_prompt,
                **kwargs,
            ):
                now = perf_counter()

                if first_content_at is None and _is_content_event(event):
                    first_content_at = now

                metadata = _find_metadata(event)
                if metadata is not None:
                    provider_metadata.update(metadata)

                # Preserve the original Strands streaming behaviour.
                yield event

            success = True

        finally:
            finished_at = perf_counter()

            usage = provider_metadata.get("usage") or {}
            provider_metrics = provider_metadata.get("metrics") or {}

            provider_latency = provider_metrics.get("latencyMs")
            measured_latency = (finished_at - started_at) * 1000

            ttfb = provider_metrics.get("timeToFirstByteMs")

            if ttfb is None and first_content_at is not None:
                ttfb = (first_content_at - started_at) * 1000

            model_metrics.record_call(
                usage=usage,
                latency_ms=(
                    float(provider_latency)
                    if provider_latency is not None
                    else measured_latency
                ),
                ttfb_ms=float(ttfb) if ttfb is not None else None,
                success=success,
            )


def build_agent() -> Agent:
    """Construct the Strands agent using Amazon Bedrock."""
    model_id = os.getenv("BEDROCK_MODEL_ID", "").strip()
    region = os.getenv("AWS_REGION", "").strip()

    if not model_id:
        raise RuntimeError(
            "BEDROCK_MODEL_ID must be configured before starting the agent."
        )

    model_options: dict[str, object] = {
        "model_id": model_id,
        "max_tokens": 1024,
    }

    if region:
        model_options["region_name"] = region

    model = ObservedBedrockModel(**model_options)

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            search_banking_policy,
            verify_customer,
            get_customer_accounts,
            get_balance,
            get_mini_statement,
            get_transaction_status,
            open_dispute,
            block_card,
            check_loan_eligibility,
            get_loan_status,
            handoff_to_human,
            create_confirmation,
            approve_confirmation,
        ],
    )