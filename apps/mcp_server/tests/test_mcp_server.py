"""Tests for the Rubies MFB MCP server."""

import asyncio
import json

from mcp.shared.memory import create_connected_server_and_client_session

from rubies_mcp_server import server as server_module
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