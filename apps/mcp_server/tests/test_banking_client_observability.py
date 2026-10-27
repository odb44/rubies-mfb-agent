import asyncio
from typing import Any

import httpx
import pytest

from rubies_observability import correlation_context
from rubies_mcp_server.banking_client import BankingAPIClient


captured_requests: list[dict[str, Any]] = []


class FakeResponse:
    status_code = 200

    def json(self) -> dict[str, Any]:
        return {
            "reference": "TXN-TEST-001",
            "status": "SUCCESS",
        }


class FakeAsyncClient:
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

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
    ) -> FakeResponse:
        captured_requests.append(
            {
                "url": url,
                "headers": headers.copy(),
            }
        )
        await asyncio.sleep(0)
        return FakeResponse()


@pytest.fixture(autouse=True)
def isolate_captured_requests():
    captured_requests.clear()
    yield
    captured_requests.clear()


def test_banking_request_forwards_correlation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        client = BankingAPIClient("http://banking.test")

        with correlation_context("correlation-test-001"):
            result = await client.get_transaction_status(
                "TXN-TEST-001",
                access_token="test-access-token",
            )

        assert result["status"] == "SUCCESS"
        assert len(captured_requests) == 1

        headers = captured_requests[0]["headers"]

        assert headers["X-Correlation-ID"] == "correlation-test-001"
        assert headers["Authorization"] == "Bearer test-access-token"

    asyncio.run(scenario())


def test_concurrent_requests_keep_correlation_ids_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        client = BankingAPIClient("http://banking.test")

        async def make_request(correlation_id: str) -> None:
            with correlation_context(correlation_id):
                await client.get_transaction_status(
                    "TXN-TEST-001",
                    access_token="test-access-token",
                )

        await asyncio.gather(
            make_request("request-alpha"),
            make_request("request-beta"),
        )

        assert len(captured_requests) == 2

        forwarded_ids = {
            request["headers"]["X-Correlation-ID"]
            for request in captured_requests
        }

        assert forwarded_ids == {
            "request-alpha",
            "request-beta",
        }

    asyncio.run(scenario())