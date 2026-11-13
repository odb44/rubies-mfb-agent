"""Support Tools for the Rubies MFB support agent."""

from typing import Any

from strands import tool

from rubies_agent.services.banking_tool_executor import call_banking_tool


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
        return await call_banking_tool("handoff_to_human", arguments)
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }
