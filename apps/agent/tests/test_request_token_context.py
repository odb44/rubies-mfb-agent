"""Tests for request-scoped authentication token isolation."""

import asyncio

import pytest
from rubies_agent.request_context import (
    _get_request_access_token,
    reset_request_access_token,
    set_request_access_token,
)


def test_missing_request_token_fails_closed() -> None:
    """Direct Banking API calls must not proceed without a request token."""
    with pytest.raises(
        RuntimeError,
        match="authenticated customer access token is required",
    ):
        _get_request_access_token()


def test_reset_restores_previous_token_context() -> None:
    """Resetting a nested context must restore the previous token."""
    customer_a_context = set_request_access_token("customer-a-token")

    try:
        assert _get_request_access_token() == "customer-a-token"

        customer_b_context = set_request_access_token("customer-b-token")

        try:
            assert _get_request_access_token() == "customer-b-token"
        finally:
            reset_request_access_token(customer_b_context)

        assert _get_request_access_token() == "customer-a-token"
    finally:
        reset_request_access_token(customer_a_context)

    with pytest.raises(RuntimeError):
        _get_request_access_token()


def test_concurrent_requests_keep_tokens_isolated() -> None:
    """Concurrent tasks must retain their own request's token."""

    async def read_request_token(token: str) -> str:
        context = set_request_access_token(token)

        try:
            await asyncio.sleep(0)
            assert _get_request_access_token() == token

            await asyncio.sleep(0)
            return _get_request_access_token()
        finally:
            reset_request_access_token(context)

    async def run_concurrent_requests() -> list[str]:
        return await asyncio.gather(
            read_request_token("customer-a-token"),
            read_request_token("customer-b-token"),
        )

    results = asyncio.run(run_concurrent_requests())

    assert results == [
        "customer-a-token",
        "customer-b-token",
    ]

    with pytest.raises(RuntimeError):
        _get_request_access_token()
