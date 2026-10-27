"""HTTP client for the Rubies MFB Banking API."""

from typing import Any
from urllib.parse import quote

import httpx
from rubies_observability import get_correlation_id


class BankingAPIError(Exception):
    """Raised when the Banking API cannot fulfil a request."""


class BankingAPIClient:
    """Call the Banking API using request-specific customer credentials."""

    def __init__(
        self,
        base_url: str,
        access_token: str | None = None,
        *,
        timeout: float = 10.0,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Banking API base URL is required.")

        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")

        if access_token is not None and not access_token.strip():
            raise ValueError("A valid access token is required.")

        self.base_url = base_url.rstrip("/")
        # Retained temporarily for compatibility with existing callers.
        # Authenticated MCP requests should pass access_token explicitly.
        self._legacy_access_token = access_token
        self.timeout = timeout

    def _resolve_access_token(self, access_token: str | None) -> str:
        """Resolve credentials, preferring the current request's token."""

        if access_token is not None and not access_token.strip():
            raise ValueError("A valid access token is required.")

        token = access_token or self._legacy_access_token

        if token is None or not token.strip():
            raise BankingAPIError(
                "A trusted session access token is required."
            )

        return token.strip()

    @staticmethod
    def _request_headers(token: str) -> dict[str, str]:
        """Build safe request headers, propagating the correlation ID."""

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        correlation_id = get_correlation_id()
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        return headers

    async def _get(
        self,
        path: str,
        *,
        resource_name: str,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Perform an authenticated GET request and validate its response."""

        token = self._resolve_access_token(access_token)
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    url,
                    headers=self._request_headers(token),
                )
        except httpx.TimeoutException as exc:
            raise BankingAPIError(
                "The Banking API request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise BankingAPIError(
                "The Banking API could not be reached."
            ) from exc

        if response.status_code == 401:
            raise BankingAPIError(
                "Authentication is required or the session has expired."
            )

        if response.status_code == 403:
            raise BankingAPIError(
                f"The {resource_name} is not available to this customer."
            )

        if response.status_code == 404:
            raise BankingAPIError(
                f"{resource_name.capitalize()} not found."
            )

        if response.status_code >= 400:
            raise BankingAPIError(
                f"The Banking API returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise BankingAPIError(
                "The Banking API returned invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise BankingAPIError(
                "The Banking API returned an unexpected response."
            )

        return payload

    async def create_support_handoff(
        self,
        *,
        reason: str,
        summary: str,
        route: str,
        priority: str,
        actions_attempted: list[str],
        unresolved_questions: list[str],
        correlation_id: str | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Queue a support handoff for the authenticated customer."""

        token = self._resolve_access_token(access_token)

        effective_correlation_id = (
            correlation_id or get_correlation_id()
        )

        payload = {
            "reason": reason,
            "summary": summary,
            "route": route,
            "priority": priority,
            "actions_attempted": actions_attempted,
            "unresolved_questions": unresolved_questions,
            "correlation_id": effective_correlation_id,
        }

        headers = self._request_headers(token)
        if effective_correlation_id:
            headers["X-Correlation-ID"] = effective_correlation_id

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/api/support-handoffs",
                    headers={
                        **headers,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise BankingAPIError(
                "The support handoff request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise BankingAPIError(
                "The Banking API could not be reached."
            ) from exc

        if response.status_code == 401:
            raise BankingAPIError(
                "Authentication is required or the session has expired."
            )

        if response.status_code == 403:
            raise BankingAPIError(
                "You are not authorized to request this handoff."
            )

        if response.status_code >= 400:
            raise BankingAPIError(
                "The Banking API could not queue the handoff "
                f"(HTTP {response.status_code})."
            )

        try:
            result = response.json()
        except ValueError as exc:
            raise BankingAPIError(
                "The Banking API returned invalid handoff data."
            ) from exc

        if not isinstance(result, dict):
            raise BankingAPIError(
                "The Banking API returned an unexpected handoff response."
            )

        if not result.get("reference") or not result.get("status"):
            raise BankingAPIError(
                "The Banking API returned an incomplete handoff response."
            )

        return result

    async def get_transaction_status(
        self,
        transaction_reference: str,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a transaction status through the authorized Banking API."""

        reference = transaction_reference.strip()

        if not reference:
            raise ValueError("Transaction reference is required.")

        encoded_reference = quote(reference, safe="")

        return await self._get(
            f"/api/transactions/{encoded_reference}/status",
            resource_name="transaction",
            access_token=access_token,
        )

    async def get_loan_status(
        self,
        loan_reference: str,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a loan status through the authorized Banking API."""

        reference = loan_reference.strip()

        if not reference:
            raise ValueError("Loan reference is required.")

        encoded_reference = quote(reference, safe="")

        return await self._get(
            f"/api/loans/{encoded_reference}/status",
            resource_name="loan",
            access_token=access_token,
        )
