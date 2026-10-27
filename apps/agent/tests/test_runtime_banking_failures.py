"""Tests for banking tool failure handling in the agent runtime."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from rubies_agent import runtime


def _run(coro):
    """Run an asynchronous test operation without pytest-asyncio."""
    return asyncio.run(coro)


def _mcp_result(payload, *, is_error=False):
    """Build a minimal MCP tool result for testing."""
    text = json.dumps(payload) if isinstance(payload, dict) else payload

    return SimpleNamespace(
        isError=is_error,
        content=[SimpleNamespace(text=text)],
    )


def _mock_mcp_transport(result=None):
    """Create mock MCP session and HTTP transport classes."""
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.call_tool = AsyncMock(return_value=result)

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    class FakeStreamableHTTPClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return object(), object(), object()

        async def __aexit__(self, *args):
            return False

    return session, FakeClientSession, FakeStreamableHTTPClient


def _with_token():
    """Set a request token and return its reset handle."""
    return runtime.set_request_access_token(
        "test-customer-access-token"
    )


def test_missing_request_token_is_rejected():
    """A banking tool must not run without a request access token."""

    async def scenario():
        with pytest.raises(
            RuntimeError,
            match="authenticated customer access token is required",
        ):
            await runtime._call_banking_tool(
                "get_transaction_status",
                {"transaction_reference": "TXN-001"},
            )

    _run(scenario())


def test_mcp_connection_failure_returns_controlled_error():
    """Connection failures must not expose raw exception details."""

    async def scenario():
        token_context = _with_token()

        try:
            with patch(
                "rubies_agent.runtime.streamablehttp_client",
                side_effect=ConnectionError(
                    "internal host and credential details"
                ),
            ):
                with pytest.raises(
                    RuntimeError,
                    match="banking service is temporarily unavailable",
                ) as exc_info:
                    await runtime._call_banking_tool(
                        "get_transaction_status",
                        {"transaction_reference": "TXN-001"},
                    )

            assert "internal host" not in str(exc_info.value)
        finally:
            runtime.reset_request_access_token(token_context)

    _run(scenario())


def test_mcp_tool_error_is_rejected():
    """An MCP tool error must not be treated as a successful enquiry."""

    async def scenario():
        token_context = _with_token()

        try:
            _, fake_session, fake_http = _mock_mcp_transport(
                _mcp_result(
                    {
                        "success": True,
                        "data": {"status": "SUCCESSFUL"},
                    },
                    is_error=True,
                )
            )

            with (
                patch(
                    "rubies_agent.runtime.streamablehttp_client",
                    return_value=fake_http(),
                ),
                patch(
                    "rubies_agent.runtime.ClientSession",
                    return_value=fake_session(),
                ),
            ):
                with pytest.raises(
                    RuntimeError,
                    match="banking service could not complete the request",
                ):
                    await runtime._call_banking_tool(
                        "get_transaction_status",
                        {"transaction_reference": "TXN-001"},
                    )
        finally:
            runtime.reset_request_access_token(token_context)

    _run(scenario())


def test_explicit_banking_failure_is_rejected():
    """An explicit success=false response must remain a failure."""

    async def scenario():
        token_context = _with_token()

        try:
            _, fake_session, fake_http = _mock_mcp_transport(
                _mcp_result(
                    {
                        "success": False,
                        "error": "The transaction is not available.",
                    }
                )
            )

            with (
                patch(
                    "rubies_agent.runtime.streamablehttp_client",
                    return_value=fake_http(),
                ),
                patch(
                    "rubies_agent.runtime.ClientSession",
                    return_value=fake_session(),
                ),
            ):
                with pytest.raises(
                    RuntimeError,
                    match="The transaction is not available",
                ):
                    await runtime._call_banking_tool(
                        "get_transaction_status",
                        {"transaction_reference": "TXN-001"},
                    )
        finally:
            runtime.reset_request_access_token(token_context)

    _run(scenario())


def test_response_without_success_indicator_is_rejected():
    """A response without an explicit success indicator is not trusted."""

    async def scenario():
        token_context = _with_token()

        try:
            _, fake_session, fake_http = _mock_mcp_transport(
                _mcp_result({"data": {"status": "SUCCESSFUL"}})
            )

            with (
                patch(
                    "rubies_agent.runtime.streamablehttp_client",
                    return_value=fake_http(),
                ),
                patch(
                    "rubies_agent.runtime.ClientSession",
                    return_value=fake_session(),
                ),
            ):
                with pytest.raises(
                    RuntimeError,
                    match="banking service returned an unexpected response",
                ):
                    await runtime._call_banking_tool(
                        "get_transaction_status",
                        {"transaction_reference": "TXN-001"},
                    )
        finally:
            runtime.reset_request_access_token(token_context)

    _run(scenario())


def test_malformed_json_response_is_rejected():
    """Malformed MCP response content must not be accepted."""

    async def scenario():
        token_context = _with_token()

        try:
            _, fake_session, fake_http = _mock_mcp_transport(
                _mcp_result("not valid JSON")
            )

            with (
                patch(
                    "rubies_agent.runtime.streamablehttp_client",
                    return_value=fake_http(),
                ),
                patch(
                    "rubies_agent.runtime.ClientSession",
                    return_value=fake_session(),
                ),
            ):
                with pytest.raises(
                    RuntimeError,
                    match="banking service returned an unexpected response",
                ):
                    await runtime._call_banking_tool(
                        "get_transaction_status",
                        {"transaction_reference": "TXN-001"},
                    )
        finally:
            runtime.reset_request_access_token(token_context)

    _run(scenario())


def test_successful_banking_response_is_preserved():
    """A valid successful response must be returned unchanged."""

    async def scenario():
        token_context = _with_token()

        try:
            expected = {
                "success": True,
                "data": {
                    "reference": "TXN-001",
                    "status": "SUCCESSFUL",
                },
            }

            session, fake_session, fake_http = _mock_mcp_transport(
                _mcp_result(expected)
            )

            with (
                patch(
                    "rubies_agent.runtime.streamablehttp_client",
                    return_value=fake_http(),
                ),
                patch(
                    "rubies_agent.runtime.ClientSession",
                    return_value=fake_session(),
                ),
            ):
                result = await runtime._call_banking_tool(
                    "get_transaction_status",
                    {"transaction_reference": "TXN-001"},
                )

            assert result == expected
            session.initialize.assert_awaited_once()
            session.call_tool.assert_awaited_once_with(
                "get_transaction_status",
                {"transaction_reference": "TXN-001"},
            )
        finally:
            runtime.reset_request_access_token(token_context)

    _run(scenario())