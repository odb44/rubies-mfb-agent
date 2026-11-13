"""Unit tests for confirmation and dispute agent tool wrappers."""

import asyncio
from unittest.mock import AsyncMock, patch

from rubies_agent.tools.confirmation_tools import (
    approve_confirmation,
    create_confirmation,
)
from rubies_agent.tools.dispute_tools import open_dispute


def run(coro):
    """Run an async tool wrapper without requiring pytest-asyncio."""
    return asyncio.run(coro)


def test_create_dispute_confirmation_passes_exact_payload():
    payload = {
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reported two duplicate debits.",
        "transaction_reference": "DEMO-DUP-B-003",
    }

    expected = {
        "success": True,
        "data": {"confirmation_id": "CONF-001", "status": "PENDING"},
    }

    with patch(
        "rubies_agent.tools.confirmation_tools.call_banking_tool",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_call:
        result = run(
            create_confirmation(
                action="OPEN_DISPUTE",
                payload=payload,
            )
        )

    assert result == expected
    mock_call.assert_awaited_once_with(
        "create_confirmation",
        {
            "action": "OPEN_DISPUTE",
            "payload": payload,
        },
    )


def test_approve_dispute_confirmation_passes_exact_payload():
    payload = {
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reported two duplicate debits.",
        "transaction_reference": "DEMO-DUP-B-003",
    }

    expected = {
        "success": True,
        "data": {"confirmation_id": "CONF-001", "status": "APPROVED"},
    }

    with patch(
        "rubies_agent.tools.confirmation_tools.call_banking_tool",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_call:
        result = run(
            approve_confirmation(
                confirmation_id="CONF-001",
                action="OPEN_DISPUTE",
                payload=payload,
            )
        )

    assert result == expected
    mock_call.assert_awaited_once_with(
        "approve_confirmation",
        {
            "confirmation_id": "CONF-001",
            "action": "OPEN_DISPUTE",
            "payload": payload,
        },
    )


def test_open_dispute_passes_transaction_reference():
    expected = {
        "success": True,
        "data": {"case_reference": "DSP-001", "status": "OPEN"},
    }

    with patch(
        "rubies_agent.tools.dispute_tools.call_banking_tool",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_call:
        result = run(
            open_dispute(
                confirmation_id="CONF-001",
                category="DUPLICATE_DEBIT",
                description="Customer reported two duplicate debits.",
                transaction_reference="DEMO-DUP-B-003",
            )
        )

    assert result == expected
    mock_call.assert_awaited_once_with(
        "open_dispute",
        {
            "confirmation_id": "CONF-001",
            "category": "DUPLICATE_DEBIT",
            "description": "Customer reported two duplicate debits.",
            "transaction_reference": "DEMO-DUP-B-003",
        },
    )


def test_open_dispute_omits_missing_transaction_reference():
    expected = {
        "success": True,
        "data": {"case_reference": "DSP-002", "status": "OPEN"},
    }

    with patch(
        "rubies_agent.tools.dispute_tools.call_banking_tool",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_call:
        result = run(
            open_dispute(
                confirmation_id="CONF-001",
                category="DUPLICATE_DEBIT",
                description="Customer reported two duplicate debits.",
            )
        )

    assert result == expected
    mock_call.assert_awaited_once_with(
        "open_dispute",
        {
            "confirmation_id": "CONF-001",
            "category": "DUPLICATE_DEBIT",
            "description": "Customer reported two duplicate debits.",
        },
    )


def test_open_dispute_rejects_missing_required_fields_without_backend_call():
    with patch(
        "rubies_agent.tools.dispute_tools.call_banking_tool",
        new_callable=AsyncMock,
    ) as mock_call:
        result = run(
            open_dispute(
                confirmation_id=" ",
                category="DUPLICATE_DEBIT",
                description="Customer reported two duplicate debits.",
            )
        )

    assert result["success"] is False
    assert "confirmation, category, and description" in result["error"]
    mock_call.assert_not_awaited()


def test_open_dispute_returns_backend_runtime_error():
    with patch(
        "rubies_agent.tools.dispute_tools.call_banking_tool",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Dispute confirmation is invalid."),
    ) as mock_call:
        result = run(
            open_dispute(
                confirmation_id="CONF-001",
                category="DUPLICATE_DEBIT",
                description="Customer reported two duplicate debits.",
            )
        )

    assert result == {
        "success": False,
        "error": "Dispute confirmation is invalid.",
    }
    mock_call.assert_awaited_once()
