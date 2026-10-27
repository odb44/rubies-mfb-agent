"""Tests for the MCP banking client's loan-status endpoint."""

import asyncio
from typing import Any

import httpx
import pytest
from rubies_mcp_server.banking_client import (
    BankingAPIClient,
    BankingAPIError,
)


class FakeResponse:
    """Minimal HTTP response for client tests."""

    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        *,
        invalid_json: bool = False,
    ) -> None:
        self.status_code = status_code
        self.payload = payload
        self.invalid_json = invalid_json

    def json(self) -> Any:
        if self.invalid_json:
            raise ValueError("Invalid JSON")
        return self.payload


class FakeAsyncClient:
    """Fake httpx client supporting async context management."""

    response: FakeResponse
    request_error: Exception | None = None
    last_url: str | None = None
    last_headers: dict[str, str] | None = None

    def __init__(
        self,
        *,
        timeout: float,
        follow_redirects: bool,
    ) -> None:
        self.timeout = timeout
        self.follow_redirects = follow_redirects

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        return None

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
    ) -> FakeResponse:
        type(self).last_url = url
        type(self).last_headers = headers

        if type(self).request_error is not None:
            raise type(self).request_error

        return type(self).response


@pytest.fixture(autouse=True)
def reset_fake_client() -> None:
    FakeAsyncClient.last_url = None
    FakeAsyncClient.last_headers = None
    FakeAsyncClient.request_error = None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> BankingAPIClient:
    monkeypatch.setattr(
        "rubies_mcp_server.banking_client.httpx.AsyncClient",
        FakeAsyncClient,
    )

    return BankingAPIClient(
    base_url="http://localhost:8000",
)


def test_get_loan_status_returns_api_payload(
    client: BankingAPIClient,
) -> None:
    payload = {
        "loan_reference": "LN-000001",
        "status": "ACTIVE",
        "principal": "500000.00",
        "outstanding_balance": "350000.00",
        "currency": "NGN",
        "term_months": 12,
        "disbursed_at": "2026-01-15T10:00:00Z",
    }
    FakeAsyncClient.response = FakeResponse(200, payload)

    result = asyncio.run(
                client.get_loan_status(
                "LN-000001",
                access_token="test-session-token",
    )
)

    assert result == payload
    assert result["outstanding_balance"] == "350000.00"
    assert FakeAsyncClient.last_url == (
        "http://localhost:8000/api/loans/LN-000001/status"
    )
    assert FakeAsyncClient.last_headers == {
    "Authorization": "Bearer test-session-token",
    "Accept": "application/json",
}

def test_get_loan_status_rejects_blank_reference(
    client: BankingAPIClient,
) -> None:
    with pytest.raises(ValueError, match="Loan reference is required"):
        asyncio.run(
            client.get_loan_status(
                "  ",
                access_token="test-session-token",
            )
        )


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (401, "Authentication is required"),
        (403, "not available to this customer"),
        (404, "Loan not found"),
        (500, "HTTP 500"),
    ],
)
def test_get_loan_status_maps_http_errors(
    client: BankingAPIClient,
    status_code: int,
    message: str,
) -> None:
    FakeAsyncClient.response = FakeResponse(status_code)

    with pytest.raises(BankingAPIError, match=message):
        asyncio.run(
            client.get_loan_status(
        "   LN-000001",
            access_token="test-session-token",
    )
)


def test_get_loan_status_maps_timeout(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.request_error = httpx.ReadTimeout("Timed out")

    with pytest.raises(BankingAPIError, match="timed out"):
        asyncio.run(
         client.get_loan_status(
         "LN-000001",
         access_token="test-session-token",
    )
)


def test_get_loan_status_maps_connection_error(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.request_error = httpx.ConnectError("Connection refused")

    with pytest.raises(BankingAPIError, match="could not be reached"):
        asyncio.run(
            client.get_loan_status(
            "LN-000001",
            access_token="test-session-token",
    )
)


def test_get_loan_status_rejects_invalid_json(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.response = FakeResponse(
        200,
        invalid_json=True,
    )

    with pytest.raises(BankingAPIError, match="invalid JSON"):
        asyncio.run(
            client.get_loan_status(
                "LN-000001",
                access_token="test-session-token",
            )
        )

def test_get_loan_status_rejects_non_object_response(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.response = FakeResponse(200, ["unexpected"])

    with pytest.raises(BankingAPIError, match="unexpected response"):
        asyncio.run(
            client.get_loan_status(
                "LN-000001",
                access_token="test-session-token",
            )
        )