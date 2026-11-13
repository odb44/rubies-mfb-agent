"""Identity Tools for the Rubies MFB support agent."""

from typing import Any

from strands import tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


@tool
async def verify_customer() -> dict[str, Any]:
    """Verify that the active authenticated customer session is trusted."""
    try:
        return await call_banking_tool("verify_customer", {})
    except RuntimeError as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }
