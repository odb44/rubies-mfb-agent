"""Transaction Tools for the Rubies MFB support agent."""

from typing import Any

from strands import tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


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
        return await call_banking_tool(
            "get_transaction_status",
            {"transaction_reference": reference},
        )
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }
