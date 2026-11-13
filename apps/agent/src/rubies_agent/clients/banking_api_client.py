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
        *,
        timeout: float = 10.0,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Banking API base URL is required.")

        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _resolve_access_token(self, access_token: str | None) -> str:
        """Require the current request's explicit bearer token."""

        if access_token is not None and not access_token.strip():
            raise ValueError("A valid access token is required.")

        token = access_token
        if token is None or not token.strip():
            raise BankingAPIError("A trusted session access token is required.")

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
        allow_list: bool = False,
    ) -> Any:
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
            if response.status_code == 422:
                try:
                    error_body = response.json()
                except ValueError:
                    error_body = {}

                details = error_body.get("detail", [])

                if isinstance(details, list):
                    validation_errors = "; ".join(
                        f"{'.'.join(str(part) for part in item.get('loc', []))}: "
                        f"{item.get('msg', 'Invalid value')}"
                        for item in details
                        if isinstance(item, dict)
                    )
                elif isinstance(details, str):
                    validation_errors = details
                else:
                    validation_errors = ""

                if validation_errors:
                    raise BankingAPIError(
                        f"Support handoff validation failed: {validation_errors}"
                    )

            raise BankingAPIError(
                f"The Banking API could not queue the handoff (HTTP {response.status_code})."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise BankingAPIError("The Banking API returned invalid JSON.") from exc

        if isinstance(payload, dict):
            return payload

        if allow_list and isinstance(payload, list):
            return payload

        raise BankingAPIError("The Banking API returned an unexpected response.")

    async def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        resource_name: str,
        access_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform an authenticated JSON POST and validate its response."""

        token = self._resolve_access_token(access_token)
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    url,
                    headers={
                        **self._request_headers(token),
                        "Content-Type": "application/json",
                        **(extra_headers or {})
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise BankingAPIError(f"The {resource_name} request timed out.") from exc
        except httpx.RequestError as exc:
            raise BankingAPIError("The Banking API could not be reached.") from exc

        if response.status_code == 401:
            raise BankingAPIError("Authentication is required or the session has expired.")

        if response.status_code == 403:
            raise BankingAPIError(f"The {resource_name} is not available to this customer.")

        if response.status_code == 404:
            raise BankingAPIError(f"{resource_name.capitalize()} not found.")

        if response.status_code >= 400:
            raise BankingAPIError(
                f"The Banking API returned HTTP {response.status_code} "
                f"for the {resource_name} request."
            )

        try:
            result = response.json()
        except ValueError as exc:
            raise BankingAPIError(
                f"The Banking API returned invalid {resource_name} JSON."
            ) from exc

        if not isinstance(result, dict):
            raise BankingAPIError(
                f"The Banking API returned an unexpected {resource_name} response."
            )

        return result

    async def validate_session(
        self,
        *,
        access_token: str,
    ) -> dict[str, Any]:
        """Validate a customer session through the authoritative Banking API."""
        payload = await self._get(
            "/api/auth/session",
            resource_name="customer session",
            access_token=access_token,
        )
        customer_id = payload.get("customer_id")
        session_id = payload.get("session_id")
        if not isinstance(customer_id, str) or not customer_id.strip():
            raise BankingAPIError("The Banking API returned an invalid customer identity.")
        if not isinstance(session_id, str) or not session_id.strip():
            raise BankingAPIError("The Banking API returned an invalid customer session.")
        return {"customer_id": customer_id, "session_id": session_id}

    async def get_customer_accounts(
        self,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve active accounts belonging to the authenticated customer."""
        payload = await self._get(
            "/api/accounts/me",
            resource_name="customer accounts",
            access_token=access_token,
        )

        if payload.get("success") is not True:
            raise BankingAPIError(
                "The Banking API returned an unexpected customer accounts response."
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise BankingAPIError("The Banking API returned invalid customer accounts data.")

        accounts = data.get("accounts")
        count = data.get("count")

        if not isinstance(accounts, list) or not isinstance(count, int):
            raise BankingAPIError("The Banking API returned invalid customer accounts data.")

        if count != len(accounts):
            raise BankingAPIError(
                "The Banking API returned an inconsistent customer accounts count."
            )

        for account in accounts:
            if not isinstance(account, dict):
                raise BankingAPIError("The Banking API returned an invalid account entry.")

            if (
                not isinstance(account.get("account_reference"), str)
                or not account["account_reference"].strip()
                or account.get("status") != "ACTIVE"
                or not isinstance(account.get("currency"), str)
            ):
                raise BankingAPIError("The Banking API returned incomplete account information.")

        return payload

    async def get_balance(
        self,
        account_reference: str,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Get the balance of an account scoped by the Banking API to its owner."""
        reference = account_reference.strip()
        if not reference:
            raise ValueError("Account reference is required.")

        payload = await self._get(
            f"/api/accounts/{quote(reference, safe='')}/balance",
            resource_name="account",
            access_token=access_token,
        )

        if payload.get("success") is False:
            return payload

        if payload.get("success") is True:
            return payload

        # The Banking API's balance endpoint returns its data under "data".
        # Reject unexpected response shapes rather than claiming success.
        raise BankingAPIError("The Banking API returned an unexpected balance response.")

    async def get_mini_statement(
        self,
        account_reference: str,
        *,
        limit: int = 10,
        offset: int = 0,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Get a bounded mini-statement for the authenticated customer's account."""
        reference = account_reference.strip()
        if not reference or not 1 <= limit <= 50 or offset < 0:
            raise ValueError(
                "A valid account reference, limit (1-50), and non-negative offset are required."
            )
        payload = await self._get(
            (
                f"/api/accounts/{quote(reference, safe='')}/mini-statement"
                f"?limit={limit}&offset={offset}"
            ),
            resource_name="account statement",
            access_token=access_token,
        )
        return {"success": True, "data": payload}

    async def open_dispute(
        self,
        *,
        confirmation_id: str,
        category: str,
        description: str,
        transaction_reference: str | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Create a dispute and verify the Banking API confirms it is open."""

        payload = {
            "confirmation_id": confirmation_id,
            "category": category,
            "description": description,
        }

        if transaction_reference:
            payload["transaction_reference"] = transaction_reference

        result = await self._post_json(
            "/api/disputes",
            payload,
            resource_name="dispute",
            access_token=access_token,
        )

        # HTTP success alone does not prove that a dispute was created.
        case_reference = result.get("case_reference")
        if not isinstance(case_reference, str) or not case_reference.strip():
            raise BankingAPIError("The Banking API returned an invalid dispute reference.")

        if result.get("status") != "OPEN":
            raise BankingAPIError("The Banking API did not confirm that the dispute is open.")

        return {"success": True, "data": result}

    async def get_customer_cards(
        self,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve cards belonging to the authenticated customer."""
        payload = await self._get(
            "/api/cards",
            resource_name="customer cards",
            access_token=access_token,
        )

        items = payload.get("items") if isinstance(payload, dict) else None

        if not isinstance(items, list):
            raise BankingAPIError(
                "The Banking API returned invalid customer cards data."
            )

        required_fields = {
            "card_reference",
            "masked_number",
            "card_type",
            "status",
        }

        for item in items:
            if not isinstance(item, dict) or not required_fields.issubset(item):
                raise BankingAPIError(
                    "The Banking API returned an invalid card record."
                )

        return {"success": True, "data": {"items": items}}

    async def block_card(
        self, *, card_reference: str, confirmation_id: str, access_token: str | None = None
    ) -> dict[str, Any]:
        """Block a card and verify the API confirms the resulting blocked state."""
        reference = card_reference.strip()
        confirmation = confirmation_id.strip()
        if not reference:
            raise ValueError("Card reference is required.")
        if not confirmation:
            raise ValueError("Confirmation ID is required.")

        result = await self._post_json(
            f"/api/cards/{quote(reference, safe='')}/block",
            {"confirmation_id": confirmation},
            resource_name="card",
            access_token=access_token,
        )

        # HTTP 2xx alone is not proof that the card was blocked. Validate the
        # authoritative response before returning success to the agent.
        if result.get("card_reference") != reference:
            raise BankingAPIError("The Banking API response did not match the requested card.")
        if result.get("status") != "BLOCKED":
            raise BankingAPIError("The Banking API did not confirm that the card is blocked.")

        return {"success": True, "data": result}

    async def create_confirmation(
        self,
        *,
        action: str,
        payload: dict[str, str],
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Create a pending confirmation bound to the authenticated session."""

        normalized_action = action.strip().upper()

        if normalized_action not in {"BLOCK_CARD", "OPEN_DISPUTE"}:
            raise ValueError("Unsupported confirmation action.")

        if normalized_action == "BLOCK_CARD":
            card_reference = payload.get("card_reference", "").strip()
            if not card_reference:
                raise ValueError("Card reference is required.")

            payload = {"card_reference": card_reference}

        result = await self._post_json(
            "/api/confirmations",
            {
                "action": normalized_action,
                "payload": payload,
            },
            resource_name="confirmation",
            access_token=access_token,
        )

        if not isinstance(result.get("confirmation_id"), str) or result.get("status") != "PENDING":
            raise BankingAPIError("The Banking API returned an invalid confirmation response.")

        return {"success": True, "data": result}

    async def approve_confirmation(
        self,
        *,
        confirmation_id: str,
        action: str,
        payload: dict[str, str],
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Approve a pending confirmation for its exact action and payload."""

        confirmation_id = confirmation_id.strip()
        normalized_action = action.strip().upper()

        if not confirmation_id:
            raise ValueError("Confirmation ID is required.")

        if normalized_action not in {"BLOCK_CARD", "OPEN_DISPUTE"}:
            raise ValueError("Unsupported confirmation action.")

        if normalized_action == "BLOCK_CARD":
            card_reference = payload.get("card_reference", "").strip()
            if not card_reference:
                raise ValueError("Card reference is required.")

            payload = {"card_reference": card_reference}

        result = await self._post_json(
            "/api/confirmations/approve",
            {
                "confirmation_id": confirmation_id,
                "action": normalized_action,
                "payload": payload,
            },
            resource_name="confirmation",
            access_token=access_token,
        )

        if (
            result.get("confirmation_id") != confirmation_id
            or result.get("action") != normalized_action
            or result.get("status") != "APPROVED"
        ):
            raise BankingAPIError("The Banking API did not confirm approval.")

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

        effective_correlation_id = correlation_id or get_correlation_id()

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
            raise BankingAPIError("The support handoff request timed out.") from exc
        except httpx.RequestError as exc:
            raise BankingAPIError("The Banking API could not be reached.") from exc

        if response.status_code == 401:
            raise BankingAPIError("Authentication is required or the session has expired.")

        if response.status_code == 403:
            raise BankingAPIError("You are not authorized to request this handoff.")

        if response.status_code >= 400:
            raise BankingAPIError(
                f"The Banking API could not queue the handoff (HTTP {response.status_code})."
            )

        try:
            result = response.json()
        except ValueError as exc:
            raise BankingAPIError("The Banking API returned invalid handoff data.") from exc

        if not isinstance(result, dict):
            raise BankingAPIError("The Banking API returned an unexpected handoff response.")

        if not result.get("reference") or not result.get("status"):
            raise BankingAPIError("The Banking API returned an incomplete handoff response.")

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

        payload = await self._get(
            f"/api/transactions/{encoded_reference}/status",
            resource_name="transaction",
            access_token=access_token,
        )
        if not isinstance(payload.get("reference"), str) or not isinstance(
            payload.get("status"), str
        ):
            raise BankingAPIError(
                "The Banking API returned an invalid transaction status response."
            )
        return {"success": True, "data": payload}

    async def get_loan_status(
        self,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve all loans and applications for the authenticated customer."""

        payload = await self._get(
            "/api/loans/status",
            resource_name="customer loans",
            access_token=access_token,
        )

        if not isinstance(payload, dict):
            raise BankingAPIError("The Banking API returned invalid customer loan information.")

        loans = payload.get("loans")
        applications = payload.get("applications")

        if not isinstance(loans, list) or not isinstance(applications, list):
            raise BankingAPIError("The Banking API returned incomplete loan information.")

        loan_required_fields = {
            "loan_reference": str,
            "status": str,
            "principal": (str, int, float),
            "outstanding_balance": (str, int, float),
            "currency": str,
            "term_months": int,
            "disbursed_at": str,
        }

        application_required_fields = {
            "application_reference": str,
            "status": str,
            "requested_amount": (str, int, float),
            "currency": str,
            "purpose": str,
            "applied_at": str,
            "created_at": str,
        }

        def validate_records(
            records: list,
            required_fields: dict,
            resource_name: str,
        ) -> None:
            for record in records:
                if not isinstance(record, dict):
                    raise BankingAPIError(
                        f"The Banking API returned an invalid {resource_name} entry."
                    )

                for field, expected_type in required_fields.items():
                    value = record.get(field)

                    if (
                        not isinstance(value, expected_type)
                        or isinstance(value, bool)
                        or (isinstance(value, str) and not value.strip())
                    ):
                        raise BankingAPIError(
                            f"The Banking API returned incomplete {resource_name} information."
                        )

        validate_records(
            loans,
            loan_required_fields,
            "loan",
        )

        validate_records(
            applications,
            application_required_fields,
            "loan application",
        )

        allowed_loan_statuses = {"ACTIVE", "OVERDUE", "REPAID"}

        for loan in loans:
            if loan["status"] not in allowed_loan_statuses:
                raise BankingAPIError("The Banking API returned an unexpected loan status.")

            if loan["term_months"] <= 0:
                raise BankingAPIError("The Banking API returned an invalid loan term.")

            next_date = loan.get("next_repayment_date")
            next_amount = loan.get("next_repayment_amount")

            if (next_date is None) != (next_amount is None):
                raise BankingAPIError(
                    "The Banking API returned incomplete next repayment information."
                )

            if next_date is not None and (not isinstance(next_date, str) or not next_date.strip()):
                raise BankingAPIError("The Banking API returned an invalid repayment date.")

            if next_amount is not None and (
                not isinstance(next_amount, (str, int, float)) or isinstance(next_amount, bool)
            ):
                raise BankingAPIError("The Banking API returned an invalid repayment amount.")

        return {
            "success": True,
            "data": {
                "loans": loans,
                "applications": applications,
                "loan_count": len(loans),
                "application_count": len(applications),
            },
        }


    async def check_loan_eligibility(
            self,
            *,
            product_code: str,
            requested_amount: str,
            term_months: int,
            access_token: str | None = None,
        ) -> dict[str, Any]:
            """Request a preliminary loan eligibility assessment."""

            result = await self._post_json(
                "/api/loans/eligibility/check",
                {
                    "product_code": product_code,
                    "requested_amount": requested_amount,
                    "term_months": term_months,
                },
                resource_name="loan eligibility assessment",
                access_token=access_token,
            )

            allowed_results = {
                "ELIGIBLE_FOR_REVIEW",
                "NOT_ELIGIBLE_UNDER_CURRENT_RULES",
                "INSUFFICIENT_DATA",
                "OUT_OF_SCOPE",
            }

            if result.get("result") not in allowed_results:
                raise BankingAPIError(
                    "The Banking API returned an invalid eligibility assessment."
                )

            required_fields = (
                "product_code",
                "requested_amount",
                "term_months",
                "currency",
                "reason_codes",
                "explanation",
                "policy_document_id",
                "policy_version",
                "ruleset_version",
                "assessed_at",
                "correlation_id",
            )

            if any(field not in result for field in required_fields):
                raise BankingAPIError(
                    "The Banking API returned an incomplete eligibility assessment."
                )

            return {
                "success": True,
                "data": result,
            }

    async def add_assistant_message(
        self,
        *,
        chat_id: str,
        content: str,
        access_token: str,
        service_token: str,
    ) -> dict[str, Any]:
        """Save a completed assistant response through the protected API."""
        if not service_token.strip():
            raise BankingAPIError("Agent service authentication is not configured.")

        result = await self._post_json(
            f"/api/customer/chats/{quote(chat_id, safe='')}/assistant-messages",
            {"content": content},
            resource_name="assistant message",
            access_token=access_token,
            extra_headers={"X-Agent-Service-Token": service_token},
        )

        if result.get("role") != "ASSISTANT":
            raise BankingAPIError(
                "The Banking API did not confirm the assistant message."
            )

        return result