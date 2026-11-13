"""Tests for the customer-wide Banking API loan-status endpoint."""

import asyncio
from typing import Any

import httpx
import pytest
from rubies_agent.clients.banking_api_client import (
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
        "rubies_agent.clients.banking_api_client.httpx.AsyncClient",
        FakeAsyncClient,
    )
    return BankingAPIClient(base_url="http://localhost:8000")


def valid_loan() -> dict[str, Any]:
    return {
        "loan_reference": "LN-000001",
        "status": "ACTIVE",
        "principal": "500000.00",
        "outstanding_balance": "350000.00",
        "currency": "NGN",
        "term_months": 12,
        "disbursed_at": "2026-01-15T10:00:00Z",
        "next_repayment_date": "2026-11-15",
        "next_repayment_amount": "50000.00",
    }


def valid_application() -> dict[str, Any]:
    return {
        "application_reference": "APP-000001",
        "status": "PENDING",
        "requested_amount": "750000.00",
        "currency": "NGN",
        "purpose": "Working capital",
        "applied_at": "2026-10-30T09:00:00Z",
        "created_at": "2026-10-30T09:00:00Z",
    }


def test_get_loan_status_returns_customer_loans_and_applications(
    client: BankingAPIClient,
) -> None:
    payload = {
        "loans": [valid_loan()],
        "applications": [valid_application()],
    }
    FakeAsyncClient.response = FakeResponse(200, payload)

    result = asyncio.run(client.get_loan_status(access_token="test-session-token"))

    assert result == {
        "success": True,
        "data": {
            "loans": payload["loans"],
            "applications": payload["applications"],
            "loan_count": 1,
            "application_count": 1,
        },
    }
    assert result["data"]["loans"][0]["outstanding_balance"] == "350000.00"
    assert result["data"]["applications"][0]["status"] == "PENDING"
    assert FakeAsyncClient.last_url == "http://localhost:8000/api/loans/status"
    assert FakeAsyncClient.last_headers == {
        "Authorization": "Bearer test-session-token",
        "Accept": "application/json",
    }


def test_get_loan_status_accepts_empty_customer_collections(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.response = FakeResponse(
        200,
        {"loans": [], "applications": []},
    )

    result = asyncio.run(client.get_loan_status(access_token="test-session-token"))

    assert result == {
        "success": True,
        "data": {
            "loans": [],
            "applications": [],
            "loan_count": 0,
            "application_count": 0,
        },
    }


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (401, "Authentication is required"),
        (403, "not available to this customer"),
        (404, "Customer loans not found"),
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
        asyncio.run(client.get_loan_status(access_token="test-session-token"))


def test_get_loan_status_maps_timeout(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.request_error = httpx.ReadTimeout("Timed out")

    with pytest.raises(BankingAPIError, match="timed out"):
        asyncio.run(client.get_loan_status(access_token="test-session-token"))


def test_get_loan_status_maps_connection_error(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.request_error = httpx.ConnectError("Connection refused")

    with pytest.raises(BankingAPIError, match="could not be reached"):
        asyncio.run(client.get_loan_status(access_token="test-session-token"))


def test_get_loan_status_rejects_invalid_json(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.response = FakeResponse(200, invalid_json=True)

    with pytest.raises(BankingAPIError, match="invalid JSON"):
        asyncio.run(client.get_loan_status(access_token="test-session-token"))


def test_get_loan_status_rejects_non_object_response(
    client: BankingAPIClient,
) -> None:
    FakeAsyncClient.response = FakeResponse(200, ["unexpected"])

    with pytest.raises(BankingAPIError, match="unexpected response"):
        asyncio.run(client.get_loan_status(access_token="test-session-token"))


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"loans": []}, "incomplete loan information"),
        ({"applications": []}, "incomplete loan information"),
        (
            {"loans": ["not-a-loan"], "applications": []},
            "invalid loan entry",
        ),
        (
            {"loans": [valid_loan() | {"status": "UNKNOWN"}], "applications": []},
            "unexpected loan status",
        ),
        (
            {"loans": [], "applications": [{"status": "PENDING"}]},
            "incomplete loan application information",
        ),
    ],
)
def test_get_loan_status_rejects_invalid_record_shapes(
    client: BankingAPIClient,
    payload: dict[str, Any],
    message: str,
) -> None:
    FakeAsyncClient.response = FakeResponse(200, payload)

    with pytest.raises(BankingAPIError, match=message):
        asyncio.run(client.get_loan_status(access_token="test-session-token"))


def test_get_loan_status_rejects_empty_access_token(
    client: BankingAPIClient,
) -> None:
    with pytest.raises(ValueError, match="access token"):
        asyncio.run(client.get_loan_status(access_token="   "))
