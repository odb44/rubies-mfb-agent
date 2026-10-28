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

    async def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        resource_name: str,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Perform an authenticated JSON POST and validate its response."""
        token = self._resolve_access_token(access_token)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    headers={**self._request_headers(token), "Content-Type": "application/json"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise BankingAPIError("The Banking API request timed out.") from exc
        except httpx.RequestError as exc:
            raise BankingAPIError("The Banking API could not be reached.") from exc
        if response.status_code == 401:
            raise BankingAPIError("Authentication is required or the session has expired.")
        if response.status_code == 403:
            raise BankingAPIError(f"The {resource_name} is not available to this customer.")
        if response.status_code == 404:
            raise BankingAPIError(f"{resource_name.capitalize()} not found.")
        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                detail = body.get("detail", "") if isinstance(body, dict) else ""
            except ValueError:
                pass
            raise BankingAPIError(str(detail) or f"The Banking API returned HTTP {response.status_code}.")
        try:
            result = response.json()
        except ValueError as exc:
            raise BankingAPIError("The Banking API returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise BankingAPIError("The Banking API returned an unexpected response.")
        return result

    async def get_balance(self, account_reference: str, *, access_token: str | None = None) -> dict[str, Any]:
        """Get the balance of an account scoped by the Banking API to its owner."""
        reference = account_reference.strip()
        if not reference:
            raise ValueError("Account reference is required.")
        from urllib.parse import quote
        payload = await self._get(f"/api/accounts/{quote(reference, safe='')}/balance", resource_name="account", access_token=access_token)
        return payload if payload.get("success") is True else {"success": True, "data": payload}

    async def get_mini_statement(self, account_reference: str, *, limit: int = 10, offset: int = 0, access_token: str | None = None) -> dict[str, Any]:
        """Get a bounded mini-statement for the authenticated customer's account."""
        reference = account_reference.strip()
        if not reference or not 1 <= limit <= 50 or offset < 0:
            raise ValueError("A valid account reference, limit (1-50), and non-negative offset are required.")
        from urllib.parse import quote
        payload = await self._get(f"/api/accounts/{quote(reference, safe='')}/mini-statement?limit={limit}&offset={offset}", resource_name="account statement", access_token=access_token)
        return {"success": True, "data": payload}

    async def open_dispute(self, *, confirmation_id: str, category: str, description: str, transaction_reference: str | None = None, access_token: str | None = None) -> dict[str, Any]:
        """Create a dispute after the Banking API validates explicit confirmation."""
        payload = {"confirmation_id": confirmation_id, "category": category, "description": description}
        if transaction_reference:
            payload["transaction_reference"] = transaction_reference
        result = await self._post_json("/api/disputes", payload, resource_name="dispute", access_token=access_token)
        return {"success": True, "data": result}

    async def block_card(self, *, card_reference: str, confirmation_id: str, access_token: str | None = None) -> dict[str, Any]:
        """Block a card after the Banking API validates explicit confirmation."""
        from urllib.parse import quote
        result = await self._post_json(f"/api/cards/{quote(card_reference.strip(), safe='')}/block", {"confirmation_id": confirmation_id}, resource_name="card", access_token=access_token)
        return {"success": True, "data": result}

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
