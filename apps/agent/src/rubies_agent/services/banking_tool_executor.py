"""Direct, request-scoped execution of approved Banking API operations."""

import logging
import os
from time import perf_counter
from typing import Any

from rubies_observability import configure_logging, get_correlation_id, log_event

from rubies_agent.clients.banking_api_client import BankingAPIClient, BankingAPIError
from rubies_agent.request_context import (
    get_request_access_token as _get_request_access_token,
)

configure_logging()
logger = logging.getLogger("rubies.agent")

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


async def call_banking_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Call the Banking API directly with the authenticated request token.

    The Banking API remains responsible for identity verification, resource
    ownership, authorization, confirmations, persistence, and audit logging.
    The agent only forwards the request-scoped bearer token and validates the
    returned response shape.
    """
    started = perf_counter()
    outcome = "failure"

    try:
        token = (
            access_token.strip()
            if isinstance(access_token, str) and access_token.strip()
            else _get_request_access_token()
            )
        banking_api_url = os.getenv(
            "BANKING_API_BASE_URL",
            "http://127.0.0.1:8000",
        ).strip()
        if not banking_api_url:
            raise RuntimeError("BANKING_API_BASE_URL must not be empty.")

        client = BankingAPIClient(base_url=banking_api_url)

        try:
            if tool_name == "verify_customer":
                # Validate the token and verification state at the authoritative
                # Banking API boundary without requiring the customer to hold an account.
                await client.validate_session(access_token=token)
                response = {
                    "success": True,
                    "verified": True,
                }
            elif tool_name == "get_customer_accounts":
                response = await client.get_customer_accounts(access_token=token)
            elif tool_name == "get_balance":
                response = await client.get_balance(
                    arguments["account_reference"], access_token=token
                )
            elif tool_name == "get_mini_statement":
                response = await client.get_mini_statement(
                    arguments["account_reference"],
                    limit=arguments.get("limit", 10),
                    offset=arguments.get("offset", 0),
                    access_token=token,
                )
            elif tool_name == "open_dispute":
                response = await client.open_dispute(
                    confirmation_id=arguments["confirmation_id"],
                    category=arguments["category"],
                    description=arguments["description"],
                    transaction_reference=arguments.get("transaction_reference"),
                    access_token=token,
                )
            elif tool_name == "get_customer_cards":
                response = await client.get_customer_cards(
                    access_token=token,
                )    
            elif tool_name == "block_card":
                response = await client.block_card(
                    card_reference=arguments["card_reference"],
                    confirmation_id=arguments["confirmation_id"],
                    access_token=token,
                )
            elif tool_name == "create_confirmation":
                response = await client.create_confirmation(
                    action=arguments["action"],
                    payload=arguments["payload"],
                    access_token=token,
                )
            elif tool_name == "approve_confirmation":
                response = await client.approve_confirmation(
                    confirmation_id=arguments["confirmation_id"],
                    action=arguments["action"],
                    payload=arguments["payload"],
                    access_token=token,
                )
            elif tool_name == "get_transaction_status":
                response = await client.get_transaction_status(
                    arguments["transaction_reference"], access_token=token
                )
            elif tool_name == "get_loan_status":
                response = await client.get_loan_status(
                    access_token=token,
                )
            elif tool_name == "handoff_to_human":
                route = arguments.get("route", "GENERAL_HUMAN_SUPPORT")
                priority = arguments.get("priority", "P3")
                reason = arguments["reason"].strip()
                summary = arguments["summary"].strip()
                if route not in ALLOWED_SUPPORT_ROUTES:
                    return {
                        "success": False,
                        "status": "HANDOFF_FAILED",
                        "message": "The specified support route is invalid.",
                    }
                if priority not in ALLOWED_SUPPORT_PRIORITIES:
                    return {
                        "success": False,
                        "status": "HANDOFF_FAILED",
                        "message": "The specified support priority is invalid.",
                    }
                if not reason or not summary:
                    return {
                        "success": False,
                        "status": "HANDOFF_FAILED",
                        "message": "A reason and summary are required.",
                    }
                handoff = await client.create_support_handoff(
                    reason=reason,
                    summary=summary,
                    route=route,
                    priority=priority,
                    actions_attempted=arguments.get("actions_attempted", []),
                    unresolved_questions=arguments.get("unresolved_questions", []),
                    correlation_id=get_correlation_id(),
                    access_token=token,
                )
                if not isinstance(handoff, dict):
                    raise RuntimeError("The support service returned an unexpected response.")
                reference = handoff.get("reference")
                handoff_status = handoff.get("status")
                if not reference or not handoff_status:
                    raise RuntimeError("The support request could not be confirmed as queued.")
                response = {
                    "success": True,
                    "data": {
                        "reference": reference,
                        "status": handoff_status,
                        "priority": handoff.get("priority", priority),
                        "route": handoff.get("route", route),
                        "acknowledged_at": handoff.get("acknowledged_at"),
                        "acknowledgement_reference": handoff.get("acknowledgement_reference"),
                    },
                    "message": (
                        "The support request has been queued and is awaiting "
                        "human acknowledgement. Do not claim that a human has "
                        "acknowledged the request."
                    ),
                }
            elif tool_name == "check_loan_eligibility":
                response = await client.check_loan_eligibility(
                    product_code=arguments["product_code"],
                    requested_amount=arguments["requested_amount"],
                    term_months=arguments["term_months"],
                    access_token=token,
                )
            else:
                raise RuntimeError("The requested banking operation is not supported.")
        except BankingAPIError as exc:
            # Preserve the Banking API's safe, user-actionable failure message.
            # Return a structured failure so the model does not improvise a retry
            # with a different confirmation ID or payload.
            return {
                "success": False,
                "status": "BANKING_OPERATION_FAILED",
                "message": str(exc),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("The banking service request was invalid.") from exc

        if not isinstance(response, dict):
            raise RuntimeError("The banking service returned an unexpected response.")
        if response.get("success") is False and tool_name != "check_loan_eligibility":
            error = response.get("error") or response.get("message")
            if isinstance(error, str) and error.strip():
                raise RuntimeError(error.strip())
            raise RuntimeError("The banking service could not complete the request.")
        if response.get("success") is not True and tool_name != "check_loan_eligibility":
            raise RuntimeError("The banking service returned an unexpected response.")

        outcome = "success" if response.get("success") is True else "failure"
        return response
    finally:
        try:
            log_event(
                logger,
                component="agent",
                event="banking_tool_call",
                outcome=outcome,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                metadata={"tool_name": tool_name},
            )
        except Exception:
            # Observability failures must never break banking operations.
            pass
