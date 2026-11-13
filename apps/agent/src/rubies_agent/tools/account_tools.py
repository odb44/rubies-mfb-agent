"""Account Tools for the Rubies MFB support agent."""

from typing import Any

from strands import tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


@tool
async def get_customer_accounts() -> dict[str, Any]:
    """Retrieve active accounts belonging to the authenticated customer."""
    try:
        return await call_banking_tool("get_customer_accounts", {})
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
        return await call_banking_tool(
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
    if not account_reference.strip() or not 1 <= limit <= 50 or offset < 0:
        return {
            "success": False,
            "error": ("Provide a valid account reference, limit 1-50, and non-negative offset."),
        }

    try:
        return await call_banking_tool(
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
