"""Unit tests for the Banking API HTTP client."""

import asyncio
from unittest.mock import patch

import httpx
import pytest
from rubies_agent.clients.banking_api_client import (
    BankingAPIClient,
    BankingAPIError,
)

BASE_URL = "http://banking-api.test"
ACCESS_TOKEN = "test-session-token"


def run_with_mock_http(handler, operation):
    """Run an async Banking API client operation against mocked HTTP."""

    async def scenario():
        transport = httpx.MockTransport(handler)
        original_async_client = httpx.AsyncClient

        def mocked_async_client(*args, **kwargs):
            kwargs["transport"] = transport
            return original_async_client(*args, **kwargs)

        with patch(
            "rubies_agent.clients.banking_api_client.httpx.AsyncClient",
            side_effect=mocked_async_client,
        ):
            client = BankingAPIClient(base_url=BASE_URL)
            return await operation(client)

    return asyncio.run(scenario())


def test_client_accepts_valid_base_url():
    client = BankingAPIClient(BASE_URL)

    assert client.base_url == BASE_URL
    assert client.timeout == 10.0


def test_client_removes_trailing_slash():
    client = BankingAPIClient(f"{BASE_URL}/")

    assert client.base_url == BASE_URL


def test_client_rejects_empty_base_url():
    with pytest.raises(ValueError):
        BankingAPIClient("   ")


def test_client_rejects_non_positive_timeout():
    with pytest.raises(ValueError):
        BankingAPIClient(BASE_URL, timeout=0)


def test_get_transaction_status_sends_authorization_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/transactions/TXN-001/status"
        assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["Accept"] == "application/json"

        return httpx.Response(
            200,
            json={
                "reference": "TXN-001",
                "status": "SUCCESSFUL",
                "transaction_type": "TRANSFER",
                "amount": "1000.00",
                "currency": "NGN",
                "created_at": "2026-10-31T08:00:00Z",
            },
        )

    async def operation(client):
        return await client.get_transaction_status(
            "TXN-001",
            access_token=ACCESS_TOKEN,
        )

    result = run_with_mock_http(handler, operation)

    assert result["success"] is True
    assert result["data"]["reference"] == "TXN-001"
    assert result["data"]["status"] == "SUCCESSFUL"


def test_get_balance_preserves_successful_response():
    expected = {
        "success": True,
        "data": {
            "account_reference": "ACC-001",
            "balance": "12500.00",
            "currency": "NGN",
            "status": "ACTIVE",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/accounts/ACC-001/balance"
        assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        return httpx.Response(200, json=expected)

    async def operation(client):
        return await client.get_balance("ACC-001", access_token=ACCESS_TOKEN)

    assert run_with_mock_http(handler, operation) == expected


def test_get_balance_preserves_explicit_failure():
    expected = {
        "success": False,
        "error": "The account is not available.",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=expected)

    async def operation(client):
        return await client.get_balance("ACC-001", access_token=ACCESS_TOKEN)

    assert run_with_mock_http(handler, operation) == expected


def test_get_balance_rejects_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"balance": "12500.00"})

    async def operation(client):
        return await client.get_balance("ACC-001", access_token=ACCESS_TOKEN)

    with pytest.raises(BankingAPIError, match="unexpected balance response"):
        run_with_mock_http(handler, operation)


def test_get_loan_status_sends_authorization_header():
    expected = {
        "loans": [
            {
                "loan_reference": "LOAN-001",
                "status": "ACTIVE",
                "principal": "500000.00",
                "outstanding_balance": "350000.00",
                "currency": "NGN",
                "term_months": 12,
                "disbursed_at": "2026-01-15T10:00:00Z",
                "next_repayment_date": "2026-11-15",
                "next_repayment_amount": "50000.00",
            }
        ],
        "applications": [
            {
                "application_reference": "APP-001",
                "status": "PENDING",
                "requested_amount": "750000.00",
                "currency": "NGN",
                "purpose": "Working capital",
                "applied_at": "2026-10-30T09:00:00Z",
                "created_at": "2026-10-30T09:00:00Z",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/loans/status"
        assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["Accept"] == "application/json"
        return httpx.Response(200, json=expected)

    async def operation(client):
        return await client.get_loan_status(access_token=ACCESS_TOKEN)

    result = run_with_mock_http(handler, operation)

    assert result["success"] is True
    assert result["data"]["loans"] == expected["loans"]
    assert result["data"]["applications"] == expected["applications"]
    assert result["data"]["loan_count"] == 1
    assert result["data"]["application_count"] == 1


def test_transaction_reference_is_url_encoded():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path.decode().startswith("/api/transactions/TXN%2F001/status")
        return httpx.Response(200, json={"reference": "TXN/001", "status": "SUCCESSFUL"})

    async def operation(client):
        return await client.get_transaction_status(
            "TXN/001",
            access_token=ACCESS_TOKEN,
        )

    result = run_with_mock_http(handler, operation)
    assert result["success"] is True
    assert result["data"]["status"] == "SUCCESSFUL"


def test_loan_status_does_not_require_a_loan_reference():
    expected = {"loans": [], "applications": []}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/loans/status"
        assert "?" not in str(request.url)
        return httpx.Response(200, json=expected)

    async def operation(client):
        return await client.get_loan_status(access_token=ACCESS_TOKEN)

    result = run_with_mock_http(handler, operation)
    assert result["success"] is True
    assert result["data"]["loans"] == []
    assert result["data"]["applications"] == []
    assert result["data"]["loan_count"] == 0
    assert result["data"]["application_count"] == 0


def test_transaction_status_rejects_empty_reference():
    async def scenario():
        client = BankingAPIClient(BASE_URL)

        with pytest.raises(ValueError):
            await client.get_transaction_status(
                "   ",
                access_token=ACCESS_TOKEN,
            )

    asyncio.run(scenario())


def test_transaction_status_rejects_empty_access_token():
    async def scenario():
        client = BankingAPIClient(BASE_URL)

        with pytest.raises(ValueError, match="access token"):
            await client.get_transaction_status(
                "TXN-001",
                access_token="   ",
            )

    asyncio.run(scenario())


def test_loan_status_rejects_empty_access_token():
    async def scenario():
        client = BankingAPIClient(BASE_URL)

        with pytest.raises(ValueError, match="access token"):
            await client.get_loan_status(access_token="   ")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status_code", "description"),
    [
        (401, "unauthorized"),
        (403, "forbidden"),
        (404, "not found"),
        (500, "server error"),
    ],
)
def test_transaction_status_handles_http_errors(status_code, description):
    del description  # The client raises BankingAPIError for these responses.

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "Request failed"})

    async def operation(client):
        return await client.get_transaction_status(
            "TXN-001",
            access_token=ACCESS_TOKEN,
        )

    with pytest.raises(BankingAPIError):
        run_with_mock_http(handler, operation)


def test_transaction_status_rejects_non_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="This is not JSON",
            headers={"Content-Type": "text/plain"},
        )

    async def operation(client):
        return await client.get_transaction_status(
            "TXN-001",
            access_token=ACCESS_TOKEN,
        )

    with pytest.raises(BankingAPIError):
        run_with_mock_http(handler, operation)


def test_transaction_status_rejects_non_object_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["unexpected", "list"])

    async def operation(client):
        return await client.get_transaction_status(
            "TXN-001",
            access_token=ACCESS_TOKEN,
        )

    with pytest.raises(BankingAPIError):
        run_with_mock_http(handler, operation)


def test_validate_session_returns_trusted_identity():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/auth/session"
        assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        return httpx.Response(200, json={"customer_id": "CUST-001", "session_id": "SES-001"})

    async def operation(client):
        return await client.validate_session(access_token=ACCESS_TOKEN)

    assert run_with_mock_http(handler, operation) == {
        "customer_id": "CUST-001",
        "session_id": "SES-001",
    }


def test_open_dispute_sends_correct_payload_and_accepts_valid_response():
    expected_payload = {
        "confirmation_id": "CONF-001",
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reported two debits for one transaction.",
        "transaction_reference": "DEMO-DUP-B-003",
    }

    expected_response = {
        "case_reference": "DSP-001",
        "category": "DUPLICATE_DEBIT",
        "description": "Customer reported two debits for one transaction.",
        "status": "OPEN",
        "transaction_reference": "DEMO-DUP-B-003",
        "created_at": "2026-11-01T08:00:00Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/disputes"
        assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["Content-Type"] == "application/json"

        import json

        assert json.loads(request.content) == expected_payload

        return httpx.Response(201, json=expected_response)

    async def operation(client):
        return await client.open_dispute(
            confirmation_id="CONF-001",
            category="DUPLICATE_DEBIT",
            description="Customer reported two debits for one transaction.",
            transaction_reference="DEMO-DUP-B-003",
            access_token=ACCESS_TOKEN,
        )

    result = run_with_mock_http(handler, operation)

    assert result["success"] is True
    assert result["data"] == expected_response


@pytest.mark.parametrize(
    "response_data",
    [
        {
            "category": "DUPLICATE_DEBIT",
            "description": "Customer reported two debits.",
            "status": "OPEN",
            "transaction_reference": "DEMO-DUP-B-003",
        },
        {
            "case_reference": "DSP-001",
            "category": "DUPLICATE_DEBIT",
            "description": "Customer reported two debits.",
        },
        {
            "case_reference": "DSP-001",
            "category": "DUPLICATE_DEBIT",
            "description": "Customer reported two debits.",
            "status": "PENDING",
        },
        {
            "case_reference": "DSP-001",
            "category": "DUPLICATE_DEBIT",
            "description": "Customer reported two debits.",
            "status": "",
        },
    ],
)
def test_open_dispute_rejects_invalid_success_response(response_data):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=response_data)

    async def operation(client):
        return await client.open_dispute(
            confirmation_id="CONF-001",
            category="DUPLICATE_DEBIT",
            description="Customer reported two debits.",
            transaction_reference="DEMO-DUP-B-003",
            access_token=ACCESS_TOKEN,
        )

    with pytest.raises(BankingAPIError):
        run_with_mock_http(handler, operation)
