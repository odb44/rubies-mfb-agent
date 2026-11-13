"""Dispute Tools for the Rubies MFB support agent."""

from typing import Any

from strands import tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


@tool
async def open_dispute(
    confirmation_id: str,
    category: str,
    description: str,
    transaction_reference: str | None = None,
) -> dict[str, Any]:
    """Submit a dispute only after server-approved action confirmation."""
    if not confirmation_id.strip() or not category.strip() or not description.strip():
        return {
            "success": False,
            "error": ("A valid confirmation, category, and description are required."),
        }

    arguments: dict[str, Any] = {
        "confirmation_id": confirmation_id,
        "category": category,
        "description": description,
    }

    if transaction_reference:
        arguments["transaction_reference"] = transaction_reference

    try:
        return await call_banking_tool("open_dispute", arguments)
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }
