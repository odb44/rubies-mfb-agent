"""Policy Tools for the Rubies MFB support agent."""

from typing import Any

from rubies_knowledge_base.retrieval import search_policies
from strands import tool


@tool
def search_banking_policy(query: str) -> dict[str, Any]:
    """Search approved Rubies MFB banking policies for relevant guidance.

    Use this tool for questions about banking policies, transfer failures,
    reversals, fraud, account security, fees, and related procedures.
    Results include source filenames, sections, and excerpts.
    """
    return search_policies(query)
