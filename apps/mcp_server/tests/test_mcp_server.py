"""Tests for the Rubies MFB MCP server."""

import asyncio
import json

from mcp.shared.memory import create_connected_server_and_client_session

from rubies_mcp_server import server as server_module
from rubies_mcp_server.banking_client import BankingAPIError
from rubies_mcp_server.server import create_server
from rubies_security.authentication import TokenSettings


class FakeBankingClient:
    """Fake Banking API client for MCP tool tests."""

    async def get_transaction_status(
        self,
        transaction_reference: str,
        *,
        access_token: str,
    ) -> dict:
        assert access_token == "test-session-token"

        return {
            "success": True,
            "data": {
                "reference": transaction_reference,
                "status": "SUCCESSFUL",
            },
        }

    async def get_loan_status(
        self,
        loan_reference: str,
        *,
        access_token: str,
    ) -> dict:
        assert access_token == "test-session-token"

        return {
            "success": True,
            "data": {
                "reference": loan_reference,
                "status": "ACTIVE",
            },
        }

    async def create_support_handoff(
        self,
        *,
        reason: str,
        summary: str,
        route: str,
        priority: str,
        actions_attempted: list[str],
        unresolved_questions: list[str],
        correlation_id: str | None = None,
        access_token: str,
    ) -> dict:
        assert access_token == "test-session-token"

        return {
            "success": True,
            "data": {
                "reference": "HND-TEST001",
                "status": "PENDING_ACKNOWLEDGEMENT",
                "priority": priority,
                "route": route,
                "reason": reason,
                "summary": summary,
                "acknowledged_at": None,
                "acknowledgement_reference": None,
                "correlation_id": correlation_id,
            },
        }


def _test_token_settings() -> TokenSettings:
    """Return test-only JWT settings."""
    return TokenSettings(
        secret_key="rubies-test-only-secret-key-2026-strong",
        issuer="rubies-test",
        audience="rubies-test-client",
    )


def _mock_authentication(monkeypatch) -> None:
    """Mock trusted identity and token retrieval for tool-dispatch tests."""
    monkeypatch.setattr(
        server_module,
        "_check_tool_access",
        lambda tool_name, settings: ("CUST-001", "SESSION-001"),
    )
    monkeypatch.setattr(
        server_module,
        "_get_request_token",
        lambda: "test-session-token",
    )


def test_mcp_registers_and_invokes_transaction_tool(monkeypatch) -> None:
    async def scenario() -> None:
        _mock_authentication(monkeypatch)

        server = create_server(
            FakeBankingClient(),
            token_settings=_test_token_settings(),
        )

        async with create_connected_server_and_client_session(
            server._mcp_server
        ) as client_session:
            tools = await client_session.list_tools()

            assert any(
                tool.name == "get_transaction_status"
                for tool in tools.tools
            )

            result = await client_session.call_tool(
                "get_transaction_status",
                {"transaction_reference": "TXN-001"},
            )

            assert not result.isError
            assert result.content

            payload = json.loads(result.content[0].text)

            assert payload["success"] is True
            assert payload["data"]["reference"] == "TXN-001"
            assert payload["data"]["status"] == "SUCCESSFUL"

    asyncio.run(scenario())


def test_mcp_registers_and_invokes_loan_status_tool(monkeypatch) -> None:
    async def scenario() -> None:
        _mock_authentication(monkeypatch)

        server = create_server(
            FakeBankingClient(),
            token_settings=_test_token_settings(),
        )

        async with create_connected_server_and_client_session(
            server._mcp_server
        ) as client_session:
            tools = await client_session.list_tools()

            assert any(
                tool.name == "get_loan_status"
                for tool in tools.tools
            )

            result = await client_session.call_tool(
                "get_loan_status",
                {"loan_reference": "LN-000001"},
            )

            assert not result.isError
            assert result.content

            payload = json.loads(result.content[0].text)

            assert payload["success"] is True
            assert payload["data"]["reference"] == "LN-000001"
            assert payload["data"]["status"] == "ACTIVE"

    asyncio.run(scenario())


def test_transaction_tool_does_not_hide_banking_api_failure(
    monkeypatch,
) -> None:
    class FailingBankingClient:
        async def get_transaction_status(
            self,
            transaction_reference: str,
            *,
            access_token: str,
        ) -> dict:
            raise BankingAPIError(
                "The transaction is not available to this customer."
            )

        async def get_loan_status(
            self,
            loan_reference: str,
            *,
            access_token: str,
        ) -> dict:
            raise BankingAPIError(
                "The loan is not available to this customer."
            )

    async def scenario() -> None:
        _mock_authentication(monkeypatch)

        server = create_server(
            FailingBankingClient(),
            token_settings=_test_token_settings(),
        )

        async with create_connected_server_and_client_session(
            server._mcp_server
        ) as client_session:
            result = await client_session.call_tool(
                "get_transaction_status",
                {"transaction_reference": "TXN-OTHER-CUSTOMER"},
            )

            assert result.isError or not result.content

    asyncio.run(scenario())


def test_mcp_registers_and_invokes_handoff_tool(monkeypatch) -> None:
    async def scenario() -> None:
        _mock_authentication(monkeypatch)

        server = create_server(
            FakeBankingClient(),
            token_settings=_test_token_settings(),
        )

        async with create_connected_server_and_client_session(
            server._mcp_server
        ) as client_session:
            tools = await client_session.list_tools()

            assert any(
                tool.name == "handoff_to_human"
                for tool in tools.tools
            )

            result = await client_session.call_tool(
                "handoff_to_human",
                {
                    "reason": "UNRESOLVED_TRANSACTION",
                    "summary": (
                        "The customer reports a transaction "
                        "that remains unresolved."
                    ),
                    "route": "PAYMENTS_OPERATIONS",
                    "priority": "P2",
                    "actions_attempted": [
                        "Checked transaction status"
                    ],
                    "unresolved_questions": [
                        "Why has the transaction not completed?"
                    ],
                    "correlation_id": "TEST-CORR-001",
                },
            )

            assert not result.isError
            assert result.content

            payload = json.loads(result.content[0].text)

            assert payload["success"] is True
            assert payload["data"]["reference"] == "HND-TEST001"
            assert (
                payload["data"]["status"]
                == "PENDING_ACKNOWLEDGEMENT"
            )

    asyncio.run(scenario())


def test_handoff_tool_handles_banking_api_failure(monkeypatch) -> None:
    class FailingHandoffClient(FakeBankingClient):
        async def create_support_handoff(
            self,
            *,
            reason: str,
            summary: str,
            route: str,
            priority: str,
            actions_attempted: list[str],
            unresolved_questions: list[str],
            correlation_id: str | None = None,
            access_token: str,
        ) -> dict:
            raise BankingAPIError(
                "The support handoff service is unavailable."
            )

    async def scenario() -> None:
        _mock_authentication(monkeypatch)

        server = create_server(
            FailingHandoffClient(),
            token_settings=_test_token_settings(),
        )

        async with create_connected_server_and_client_session(
            server._mcp_server
        ) as client_session:
            result = await client_session.call_tool(
                "handoff_to_human",
                {
                    "reason": "UNRESOLVED_TRANSACTION",
                    "summary": (
                        "The customer reports an unresolved transaction."
                    ),
                    "route": "PAYMENTS_OPERATIONS",
                    "priority": "P2",
                    "actions_attempted": [
                        "Checked transaction status"
                    ],
                    "unresolved_questions": [
                        "Why is the transaction unresolved?"
                    ],
                },
            )

            # A failed API request must not produce a success response.
            assert result.isError or result.content

            if result.content:
                payload = json.loads(result.content[0].text)
                assert payload.get("success") is not True

    asyncio.run(scenario())