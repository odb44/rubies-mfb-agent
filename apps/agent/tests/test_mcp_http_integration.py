"""HTTP integration tests for the authenticated Rubies MCP server."""

import asyncio
import json
import socket
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
import jwt
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from rubies_mcp_server.server import (
    CorrelationIdMiddleware,
    create_server,
)
from rubies_security.authentication import TokenSettings


TEST_SECRET = "rubies-test-only-secret-key-2026-strong"
TEST_ISSUER = "rubies-test"
TEST_AUDIENCE = "rubies-test-client"
CORRELATION_HEADER = "X-Correlation-ID"


class FakeBankingClient:
    """Fake Banking API client; no live banking service is contacted."""

    async def get_transaction_status(
        self,
        transaction_reference: str,
        *,
        access_token: str,
    ) -> dict[str, Any]:
        assert access_token
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
    ) -> dict[str, Any]:
        assert access_token
        return {
            "success": True,
            "data": {
                "reference": loan_reference,
                "status": "ACTIVE",
            },
        }


def _token_settings() -> TokenSettings:
    """Return the JWT settings used by the test server."""
    return TokenSettings(
        secret_key=TEST_SECRET,
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
    )


def _create_token(*, verified: bool = True) -> str:
    """Create a short-lived JWT for a test customer."""
    now = int(time.time())

    return jwt.encode(
        {
            "sub": "CUST-001",
            "sid": "SESSION-001",
            "verified": verified,
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "iat": now,
            "exp": now + 300,
        },
        TEST_SECRET,
        algorithm="HS256",
    )


def _free_port() -> int:
    """Reserve an available localhost port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@asynccontextmanager
async def _running_mcp_server():
    """Run the real FastMCP HTTP transport with correlation middleware."""
    server = create_server(
        FakeBankingClient(),
        token_settings=_token_settings(),
    )

    app = server.streamable_http_app()
    app.add_middleware(CorrelationIdMiddleware)

    port = _free_port()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        lifespan="on",
    )
    uvicorn_server = uvicorn.Server(config)
    thread = threading.Thread(
        target=uvicorn_server.run,
        daemon=True,
    )
    thread.start()

    base_url = f"http://127.0.0.1:{port}/mcp"

    try:
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            if not thread.is_alive():
                raise RuntimeError(
                    "MCP HTTP server stopped during startup."
                )

            try:
                async with httpx.AsyncClient(timeout=0.5) as client:
                    response = await client.get(base_url)

                    # A 4xx response is acceptable: it proves the
                    # endpoint is reachable without an MCP POST.
                    if response.status_code < 500:
                        break

            except httpx.HTTPError:
                pass

            await asyncio.sleep(0.1)

        else:
            raise RuntimeError(
                "MCP HTTP server did not start in time."
            )

        yield base_url

    finally:
        uvicorn_server.should_exit = True
        await asyncio.to_thread(thread.join, 5)


async def _call_transaction_tool(
    base_url: str,
    token: str,
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Call the transaction tool through the real MCP HTTP transport."""
    headers = {"Authorization": f"Bearer {token}"}

    if correlation_id is not None:
        headers[CORRELATION_HEADER] = correlation_id

    async with httpx.AsyncClient(
        headers=headers,
        timeout=10,
    ) as http_client:
        async with streamable_http_client(
            base_url,
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "get_transaction_status",
                    {"transaction_reference": "TXN-HTTP-001"},
                )

                assert not result.isError
                assert result.content

                return json.loads(result.content[0].text)


async def _post_initialize_request(
    base_url: str,
    token: str,
    *,
    correlation_id: str | None = None,
) -> httpx.Response:
    """Send an MCP initialize request using the supplied bearer token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    if correlation_id is not None:
        headers[CORRELATION_HEADER] = correlation_id

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {
                "name": "rubies-auth-test",
                "version": "1.0.0",
            },
        },
    }

    async with httpx.AsyncClient(timeout=10) as client:
        return await client.post(
            base_url,
            headers=headers,
            json=payload,
        )


def test_authenticated_transaction_tool_over_real_http_transport() -> None:
    """A verified customer can invoke the transaction tool over HTTP."""

    async def scenario() -> None:
        async with _running_mcp_server() as base_url:
            result = await _call_transaction_tool(
                base_url,
                _create_token(),
            )

            assert result["success"] is True
            assert result["data"]["reference"] == "TXN-HTTP-001"
            assert result["data"]["status"] == "SUCCESSFUL"

    asyncio.run(scenario())


def test_mcp_http_propagates_valid_correlation_id() -> None:
    """A valid incoming correlation ID is preserved in the response."""

    async def scenario() -> None:
        correlation_id = "agent-integration-test-001"

        async with _running_mcp_server() as base_url:
            response = await _post_initialize_request(
                base_url,
                _create_token(),
                correlation_id=correlation_id,
            )

            assert response.status_code < 500
            assert response.headers.get(CORRELATION_HEADER) == correlation_id

    asyncio.run(scenario())


def test_mcp_http_replaces_invalid_correlation_id() -> None:
    """An invalid incoming correlation ID is replaced with a safe ID."""

    async def scenario() -> None:
        async with _running_mcp_server() as base_url:
            response = await _post_initialize_request(
                base_url,
                _create_token(),
                correlation_id="invalid correlation id with spaces",
            )

            assert response.status_code < 500

            returned_id = response.headers.get(CORRELATION_HEADER)
            assert returned_id is not None
            assert 1 <= len(returned_id) <= 64
            assert all(
                character.isalnum() or character in "._-"
                for character in returned_id
            )
            assert returned_id != "invalid correlation id with spaces"

    asyncio.run(scenario())


def test_mcp_http_rejects_invalid_token() -> None:
    """A malformed bearer token must not initialize an MCP session."""

    async def scenario() -> None:
        async with _running_mcp_server() as base_url:
            response = await _post_initialize_request(
                base_url,
                "this-is-not-a-valid-jwt",
            )

            assert response.status_code in (401, 403), (
                "Expected invalid-token rejection, "
                f"received HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

    asyncio.run(scenario())


def test_mcp_http_rejects_unverified_customer() -> None:
    """A validly signed but unverified customer's token must be rejected."""

    async def scenario() -> None:
        async with _running_mcp_server() as base_url:
            response = await _post_initialize_request(
                base_url,
                _create_token(verified=False),
            )

            assert response.status_code in (401, 403), (
                "Expected unverified-customer rejection, "
                f"received HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

    asyncio.run(scenario())