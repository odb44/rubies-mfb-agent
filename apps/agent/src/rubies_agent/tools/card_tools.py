"""Card Tools for the Rubies MFB support agent."""

from typing import Any

from strands import tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


@tool
async def get_customer_cards() -> dict[str, Any]:
    """Retrieve cards belonging to the authenticated customer."""
    try:
        return await call_banking_tool("get_customer_cards", {})
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
        return await call_banking_tool(
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
