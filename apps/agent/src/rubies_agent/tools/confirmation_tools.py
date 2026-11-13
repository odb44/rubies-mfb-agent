"""Confirmation Tools for the Rubies MFB support agent."""

from strands import tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


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

    return await call_banking_tool(
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

    return await call_banking_tool(
        "approve_confirmation",
        {
            "confirmation_id": confirmation_id,
            "action": action.strip().upper(),
            "payload": payload,
        },
    )
