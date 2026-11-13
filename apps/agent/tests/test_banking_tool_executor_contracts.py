"""Contract tests for every operation routed by banking_tool_executor."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from rubies_agent import request_context
from rubies_agent.clients.banking_api_client import BankingAPIError
from rubies_agent.orchestration.tool_policy import get_registered_tools
from rubies_agent.services import banking_tool_executor as executor


def run(coro):
    return asyncio.run(coro)


def test_registered_tool_inventory():
    """Detect accidental removal or renaming of registered agent tools."""
    expected = {
        "search_banking_policy",
        "verify_customer",
        "get_customer_accounts",
        "get_balance",
        "get_mini_statement",
        "get_transaction_status",
        "open_dispute",
        "block_card",
        "check_loan_eligibility",
        "get_loan_status",
        "handoff_to_human",
        "create_confirmation",
        "approve_confirmation",
        "assess_loan_delinquency_risk",
    }

    registered = {tool.__name__ for tool in get_registered_tools()}

    assert registered == expected
    assert len(registered) == 14


@pytest.mark.parametrize(
    ("tool_name", "arguments", "client_method", "expected_kwargs"),
    [
        (
            "verify_customer",
            {},
            "validate_session",
            {"access_token": "test-token"},
        ),
        (
            "get_customer_accounts",
            {},
            "get_customer_accounts",
            {"access_token": "test-token"},
        ),
        (
            "get_balance",
            {"account_reference": "ACC-001"},
            "get_balance",
            {"account_reference": "ACC-001", "access_token": "test-token"},
        ),
        (
            "get_mini_statement",
            {"account_reference": "ACC-001", "limit": 5, "offset": 2},
            "get_mini_statement",
            {
                "account_reference": "ACC-001",
                "limit": 5,
                "offset": 2,
                "access_token": "test-token",
            },
        ),
        (
            "get_transaction_status",
            {"transaction_reference": "TXN-001"},
            "get_transaction_status",
            {
                "transaction_reference": "TXN-001",
                "access_token": "test-token",
            },
        ),
        (
            "open_dispute",
            {
                "confirmation_id": "CONF-001",
                "category": "UNRECOGNIZED_TRANSACTION",
                "description": "I do not recognize this transaction",
                "transaction_reference": "TXN-001",
            },
            "open_dispute",
            {
                "confirmation_id": "CONF-001",
                "category": "UNRECOGNIZED_TRANSACTION",
                "description": "I do not recognize this transaction",
                "transaction_reference": "TXN-001",
                "access_token": "test-token",
            },
        ),
        (
            "block_card",
            {"card_reference": "CARD-001", "confirmation_id": "CONF-002"},
            "block_card",
            {
                "card_reference": "CARD-001",
                "confirmation_id": "CONF-002",
                "access_token": "test-token",
            },
        ),
        (
            "create_confirmation",
            {
                "action": "BLOCK_CARD",
                "payload": {"card_reference": "CARD-001"},
            },
            "create_confirmation",
            {
                "action": "BLOCK_CARD",
                "payload": {"card_reference": "CARD-001"},
                "access_token": "test-token",
            },
        ),
        (
            "approve_confirmation",
            {
                "confirmation_id": "CONF-002",
                "action": "BLOCK_CARD",
                "payload": {"card_reference": "CARD-001"},
            },
            "approve_confirmation",
            {
                "confirmation_id": "CONF-002",
                "action": "BLOCK_CARD",
                "payload": {"card_reference": "CARD-001"},
                "access_token": "test-token",
            },
        ),
        (
            "get_loan_status",
            {},
            "get_loan_status",
            {"access_token": "test-token"},
        ),
    ],
)
def test_executor_routes_tool_to_expected_client_method(
    tool_name, arguments, client_method, expected_kwargs
):
    async def scenario():
        context = request_context.set_request_access_token("test-token")
        try:
            fake_client = AsyncMock()
            getattr(fake_client, client_method).return_value = {
                "success": True,
                "data": {"test": "value"},
            }

            with patch.object(executor, "BankingAPIClient", return_value=fake_client):
                result = await executor.call_banking_tool(tool_name, arguments)

            if tool_name == "verify_customer":
                assert result == {"success": True, "verified": True}
            else:
                assert result == {"success": True, "data": {"test": "value"}}

            positional_arguments = {
                "get_balance": ("ACC-001",),
                "get_mini_statement": ("ACC-001",),
                "get_transaction_status": ("TXN-001",),
            }

            method_mock = getattr(fake_client, client_method)
            method_mock.assert_awaited_once()

            if tool_name in positional_arguments:
                assert method_mock.await_args.args == positional_arguments[tool_name]
                assert method_mock.await_args.kwargs == {
                    key: value
                    for key, value in expected_kwargs.items()
                    if key != "account_reference" and key != "transaction_reference"
                }
            else:
                method_mock.assert_awaited_once_with(**expected_kwargs)
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_handoff_validates_input_before_calling_api():
    async def scenario():
        context = request_context.set_request_access_token("test-token")
        try:
            with patch.object(executor, "BankingAPIClient") as client_factory:
                result = await executor.call_banking_tool(
                    "handoff_to_human",
                    {
                        "reason": "Need assistance",
                        "summary": "Customer needs help",
                        "route": "INVALID_ROUTE",
                        "priority": "P2",
                    },
                )

            assert result["success"] is False
            assert result["status"] == "HANDOFF_FAILED"
            client_factory.return_value.create_support_handoff.assert_not_called()
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_handoff_requires_nonblank_reason_and_summary():
    async def scenario():
        context = request_context.set_request_access_token("test-token")
        try:
            with patch.object(executor, "BankingAPIClient") as client_factory:
                result = await executor.call_banking_tool(
                    "handoff_to_human",
                    {"reason": "  ", "summary": "  "},
                )

            assert result["success"] is False
            assert result["status"] == "HANDOFF_FAILED"
            client_factory.return_value.create_support_handoff.assert_not_called()
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_handoff_requires_confirmed_queue_reference_and_status():
    async def scenario():
        context = request_context.set_request_access_token("test-token")
        try:
            fake_client = AsyncMock()
            fake_client.create_support_handoff.return_value = {
                "reference": "SUP-001",
                # Missing status must not be reported as a successful handoff.
            }

            with patch.object(executor, "BankingAPIClient", return_value=fake_client):
                with pytest.raises(RuntimeError, match="could not be confirmed as queued"):
                    await executor.call_banking_tool(
                        "handoff_to_human",
                        {
                            "reason": "Customer needs assistance",
                            "summary": "Unable to resolve account enquiry",
                        },
                    )
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_loan_eligibility_fails_closed_without_calling_a_lending_endpoint():
    async def scenario():
        context = request_context.set_request_access_token("test-token")
        try:
            with patch.object(executor, "BankingAPIClient") as client_factory:
                result = await executor.call_banking_tool("check_loan_eligibility", {})

            assert result["success"] is False
            assert result["status"] == "ASSESSMENT_UNAVAILABLE"
            assert "not a lending decision" in result["message"]
            client_factory.assert_called_once()
            client = client_factory.return_value
            client.check_loan_eligibility.assert_not_called()
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_executor_rejects_missing_request_token_before_creating_client():
    async def scenario():
        with patch.object(executor, "BankingAPIClient") as client_factory:
            with pytest.raises(RuntimeError):
                await executor.call_banking_tool("get_balance", {"account_reference": "ACC-001"})

            client_factory.assert_not_called()

    run(scenario())


def test_banking_api_error_is_returned_as_structured_failure():
    async def scenario():
        context = request_context.set_request_access_token("test-token")
        try:
            fake_client = AsyncMock()
            fake_client.get_balance.side_effect = BankingAPIError(
                "The Banking API could not be reached."
            )

            with patch.object(executor, "BankingAPIClient", return_value=fake_client):
                result = await executor.call_banking_tool(
                    "get_balance", {"account_reference": "ACC-001"}
                )

            assert result == {
                "success": False,
                "status": "BANKING_OPERATION_FAILED",
                "message": "The Banking API could not be reached.",
            }
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())


def test_unknown_operation_is_rejected():
    async def scenario():
        context = request_context.set_request_access_token("test-token")
        try:
            with patch.object(executor, "BankingAPIClient"):
                with pytest.raises(RuntimeError, match="operation is not supported"):
                    await executor.call_banking_tool("unknown_operation", {})
        finally:
            request_context.reset_request_access_token(context)

    run(scenario())
