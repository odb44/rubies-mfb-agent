"""Failure-path tests for direct agent-to-Banking-API calls."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from rubies_agent import request_context
from rubies_agent.clients.banking_api_client import BankingAPIError
from rubies_agent.services import banking_tool_executor as executor


def run(coro):
    return asyncio.run(coro)


def test_direct_client_connection_failure_is_controlled():
    async def scenario():
        context = request_context.set_request_access_token("trusted-token")
        try:
            fake_client = AsyncMock()
            fake_client.get_transaction_status.side_effect = BankingAPIError(
                "The Banking API could not be reached."
            )
            with patch.object(executor, "BankingAPIClient", return_value=fake_client):
                result = await executor.call_banking_tool(
                    "get_transaction_status",
                    {"transaction_reference": "TXN-001"},
                )

            assert result == {
                "success": False,
                "status": "BANKING_OPERATION_FAILED",
                "message": "The Banking API could not be reached.",
            }
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_explicit_banking_failure_is_rejected():
    async def scenario():
        context = request_context.set_request_access_token("trusted-token")
        try:
            fake_client = AsyncMock()
            fake_client.get_balance.return_value = {
                "success": False,
                "message": "Account unavailable",
            }
            with patch.object(executor, "BankingAPIClient", return_value=fake_client):
                with pytest.raises(RuntimeError, match="Account unavailable"):
                    await executor.call_banking_tool(
                        "get_balance", {"account_reference": "ACC-001"}
                    )
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_response_without_success_indicator_is_rejected():
    async def scenario():
        context = request_context.set_request_access_token("trusted-token")
        try:
            fake_client = AsyncMock()
            fake_client.get_transaction_status.return_value = {"data": {"status": "SUCCESSFUL"}}
            with patch.object(executor, "BankingAPIClient", return_value=fake_client):
                with pytest.raises(RuntimeError, match="unexpected response"):
                    await executor.call_banking_tool(
                        "get_transaction_status",
                        {"transaction_reference": "TXN-001"},
                    )
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_direct_client_never_calls_without_request_token():
    async def scenario():
        with patch.object(executor, "BankingAPIClient") as client_factory:
            with pytest.raises(RuntimeError, match="authenticated customer access token"):
                await executor.call_banking_tool(
                    "get_transaction_status",
                    {"transaction_reference": "TXN-001"},
                )
            client_factory.assert_not_called()

    run(scenario())
