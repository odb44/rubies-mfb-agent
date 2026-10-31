"""Tests for forwarding the authenticated request token to MCP."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

from rubies_agent import runtime


def test_banking_tool_forwards_request_token_to_mcp(monkeypatch) -> None:
    """The MCP connection must use the current request's bearer token."""
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def fake_streamable_http_client(url, *, headers):
        captured["url"] = url
        captured["headers"] = headers
        yield object(), object(), None

    class FakeClientSession:
        def __init__(self, read_stream, write_stream):
            captured["session_created"] = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def initialize(self):
            captured["initialized"] = True

        async def call_tool(self, tool_name, arguments):
            captured["tool_name"] = tool_name
            captured["arguments"] = arguments

            return SimpleNamespace(
                isError=False,
                content=[
                    SimpleNamespace(
                        text=json.dumps(
                            {
                                "success": True,
                                "data": {
                                    "reference": "TXN-001",
                                    "status": "SUCCESSFUL",
                                },
                            }
                        )
                    )
                ],
            )

    monkeypatch.setattr(
        runtime,
        "streamablehttp_client",
        fake_streamable_http_client,
    )
    monkeypatch.setattr(runtime, "ClientSession", FakeClientSession)

    async def scenario() -> dict:
        token_context = runtime.set_request_access_token(
            "customer-a-test-token"
        )

        try:
            return await runtime._call_banking_tool(
                "get_transaction_status",
                {"transaction_reference": "TXN-001"},
            )
        finally:
            runtime.reset_request_access_token(token_context)

    result = asyncio.run(scenario())

    assert captured["url"] == "http://127.0.0.1:8002/mcp"
    assert captured["headers"] == {
        "Authorization": "Bearer customer-a-test-token"
    }
    assert captured["tool_name"] == "get_transaction_status"
    assert captured["arguments"] == {
        "transaction_reference": "TXN-001"
    }
    assert captured["initialized"] is True
    assert result["success"] is True
    assert result["data"]["status"] == "SUCCESSFUL"
