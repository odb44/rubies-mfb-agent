"""HTTP client for the Rubies MFB Banking API."""

from typing import Any
from urllib.parse import quote

import httpx


class BankingAPIError(Exception):
    """Raised when the Banking API cannot fulfil a request."""


class BankingAPIClient:
    """Call the Banking API using request-scoped trusted credentials."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Banking API base URL is required.")
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _get(
        self,
        path: str,
        *,
        access_token: str,
        resource_name: str,
    ) -> dict[str, Any]:
        """Make a request using the current invocation's trusted token."""
        token = access_token.strip()
        if not token:
            raise ValueError("A trusted access token is required.")

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
        except httpx.TimeoutException as exc:
            raise BankingAPIError("The Banking API request timed out.") from exc
        except httpx.RequestError as exc:
            raise BankingAPIError("The Banking API could not be reached.") from exc

        if response.status_code == 401:
            raise BankingAPIError("Authentication is required or the session expired.")
        if response.status_code == 403:
            raise BankingAPIError(
                f"The {resource_name} is not available to this customer."
            )
        if response.status_code == 404:
            raise BankingAPIError(f"{resource_name.capitalize()} not found.")
        if response.status_code >= 400:
            raise BankingAPIError(
                f"The Banking API returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise BankingAPIError("The Banking API returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise BankingAPIError("The Banking API returned an unexpected response.")

        return payload

    async def get_transaction_status(
        self,
        transaction_reference: str,
        *,
        access_token: str,
    ) -> dict[str, Any]:
        """Retrieve a transaction status."""
        reference = transaction_reference.strip()
        if not reference:
            raise ValueError("Transaction reference is required.")

        return await self._get(
            f"/api/transactions/{quote(reference, safe='')}/status",
            access_token=access_token,
            resource_name="transaction",
        )

    async def get_loan_status(
        self,
        loan_reference: str,
        *,
        access_token: str,
    ) -> dict[str, Any]:
        """Retrieve a loan status."""
        reference = loan_reference.strip()
        if not reference:
            raise ValueError("Loan reference is required.")

        return await self._get(
            f"/api/loans/{quote(reference, safe='')}/status",
            access_token=access_token,
            resource_name="loan",
        )