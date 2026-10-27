"""Strands agent configuration for the Rubies MFB support agent."""

import json
import os
from contextvars import ContextVar
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from rubies_knowledge_base.retrieval import search_policies

import logging
from time import perf_counter

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
    arguments: dict[str, str],
) -> dict[str, Any]:
    """Call an authenticated banking MCP tool for the current customer."""
    started = perf_counter()
    outcome = "failure"

    try:
        token = _get_request_access_token()
        mcp_url = os.getenv(
            "MCP_SERVER_URL",
            "http://127.0.0.1:8001/mcp",
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
                tool_name=tool_name,
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
        result = await _call_banking_tool(
            "get_transaction_status",
            {"transaction_reference": reference},
        )
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return result


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
        result = await _call_banking_tool(
            "get_loan_status",
            {"loan_reference": reference},
        )
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return result

@tool
async def check_loan_eligibility(
    applicant_data: dict[str, Any],
) -> dict[str, Any]:
    """Run a historical loan-model demonstration using applicant information.

    This is not an official Rubies MFB eligibility assessment or loan decision.
    All applicant data is passed through the authenticated MCP server.
    """
    if not isinstance(applicant_data, dict):
        return {
            "success": False,
            "status": "INVALID_INPUT",
            "error": "Applicant information must be provided as an object.",
        }

    if not applicant_data:
        return {
            "success": False,
            "status": "INSUFFICIENT_INFORMATION",
            "error": "Applicant information is required.",
        }

    try:
        return await _call_banking_tool(
            "check_loan_eligibility",
            {"applicant_data": applicant_data},
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "status": "SERVICE_ERROR",
            "error": str(exc),
        }



SYSTEM_PROMPT = """
You are the Rubies MFB Customer Support Agent.

Your responsibilities:
- Help customers understand banking services and policies.
- Explain transaction statuses using verified banking information.
- Guide customers through appropriate support workflows.
-Explain historical loan-model estimates without promising loan approval.
- For loan eligibility demonstration requests, use check_loan_eligibility
  only when the applicant has supplied the required information.
- Ask for missing information rather than inventing applicant details.
- Explain that the model uses historical Kaggle loan data and is not validated
  for Rubies MFB lending decisions.
- Never describe a historical model estimate as an actual eligibility
  decision, approval, rejection, or loan offer.
- Escalate unresolved, unsafe, or sensitive issues to a human support agent.

Policy retrieval:
- For questions about banking policies, procedures, or rules, use
  search_banking_policy before answering.
- Base policy explanations on approved retrieved policy content.
- Identify the source filename and relevant section when explaining a policy.
- If no relevant policy is found, explain the limitation instead of inventing
  an official banking rule.
- Policy retrieval does not provide customer-specific account records.

Banking tools:
- Use get_transaction_status for transaction-status enquiries.
- Use get_loan_status for loan-status enquiries.
- Report banking results only when a trusted banking service returns them.
- If a tool reports failure, explain that the status could not be retrieved.
- Never treat a reference supplied by the customer as proof of identity.
- Never invent balances, transaction statuses, or customer records.
- Use check_loan_eligibility only for the historical-model demonstration.
- Treat unsuccessful tool responses as failures, not eligibility results.

Security rules:
- Never ask customers to disclose passwords, PINs, or authentication secrets.
- Never reveal access tokens or internal authentication details.
- Never claim an operation succeeded unless a trusted service confirms it.
- Never execute a sensitive state-changing operation without the required
  server-enforced authorization and explicit confirmation.
- If reliable information is unavailable, explain the limitation and offer
  an appropriate next step.

Only use the tools and policy sources explicitly provided to you.
Do not claim to have accessed a system or completed an operation when you have not.
""".strip()


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

    model = BedrockModel(**model_options)

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            search_banking_policy,
            get_transaction_status,
            get_loan_status,
            check_loan_eligibility,
        ],
    )
