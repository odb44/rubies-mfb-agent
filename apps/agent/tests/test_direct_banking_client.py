"""Tests for direct agent-to-Banking-API tool execution."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from rubies_agent import request_context
from rubies_agent.services import banking_tool_executor as executor


def _run(coro):
    return asyncio.run(coro)


def test_direct_call_requires_request_scoped_token():
    async def scenario():
        with pytest.raises(RuntimeError, match="authenticated customer access token"):
            await executor.call_banking_tool(
                "get_transaction_status",
                {"transaction_reference": "TXN-001"},
            )

    _run(scenario())


def test_transaction_status_uses_direct_banking_api_client():
    async def scenario():
        token_context = request_context.set_request_access_token("trusted-token")
        try:
            fake_client = AsyncMock()
            fake_client.get_transaction_status.return_value = {
                "success": True,
                "data": {"reference": "TXN-001", "status": "SUCCESSFUL"},
            }
            with patch.object(executor, "BankingAPIClient", return_value=fake_client):
                result = await executor.call_banking_tool(
                    "get_transaction_status",
                    {"transaction_reference": "TXN-001"},
                )

            assert result["success"] is True
            fake_client.get_transaction_status.assert_awaited_once_with(
                "TXN-001",
                access_token="trusted-token",
            )
        finally:
            request_context.reset_request_access_token(token_context)

    _run(scenario())


def test_loan_eligibility_fails_closed_without_authoritative_endpoint():
    async def scenario():
        token_context = request_context.set_request_access_token("trusted-token")
        try:
            with patch.object(executor, "BankingAPIClient") as client_factory:
                result = await executor.call_banking_tool(
                    "check_loan_eligibility",
                    {},
                )

            assert result["success"] is False
            assert result["status"] == "ASSESSMENT_UNAVAILABLE"
            client_factory.assert_called_once()
        finally:
            request_context.reset_request_access_token(token_context)

    _run(scenario())
