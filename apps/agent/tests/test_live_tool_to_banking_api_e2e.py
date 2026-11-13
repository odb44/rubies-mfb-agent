"""Live tool-to-Banking-API integration tests.

These tests use the real agent tool wrappers and the real Banking API over HTTP.
They do not mock BankingAPIClient or call_banking_tool.

Run from the repository root with the agent environment active:
    $env:RUN_LIVE_BANKING_E2E = "1"
    $env:BANKING_API_BASE_URL = "http://127.0.0.1:8000"
    $env:E2E_ACCESS_TOKEN = "<test-customer bearer token>"
    pytest .\apps\agent\tests\test_live_tool_to_banking_api_e2e.py -q

Optional references:
    E2E_TRANSACTION_REFERENCE
    E2E_LOAN_REFERENCE
    E2E_CARD_REFERENCE
    E2E_DISPUTE_TRANSACTION_REFERENCE

Sensitive/destructive scenarios are opt-in:
    E2E_ALLOW_CARD_BLOCK=1
    E2E_ALLOW_DISPUTE_CREATE=1

The suite deliberately skips scenarios whose real test data is not configured.
Skipped tests are NOT counted as passed coverage.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_BANKING_E2E") != "1",
    reason="Set RUN_LIVE_BANKING_E2E=1 to run against a live Banking API.",
)

TOKEN = os.getenv("E2E_ACCESS_TOKEN", "").strip()


def require_token() -> str:
    if not TOKEN:
        pytest.skip("E2E_ACCESS_TOKEN is not configured.")
    return TOKEN


def run(coro):
    """Run async tool wrappers without requiring pytest-asyncio."""
    import asyncio

    return asyncio.run(coro)


def with_token(coro_factory):
    """Run one real tool invocation with request-scoped bearer-token context."""
    from rubies_agent.request_context import (
        reset_request_access_token,
        set_request_access_token,
    )

    token_context = set_request_access_token(require_token())
    try:
        return run(coro_factory())
    finally:
        reset_request_access_token(token_context)


def assert_success_or_documented_domain_result(result: dict[str, Any]) -> None:
    assert isinstance(result, dict), f"Expected JSON object, got {type(result).__name__}"
    assert result.get("success") is True or result.get("success") is False, result


def test_live_verify_customer() -> None:
    from rubies_agent.tools.identity_tools import verify_customer

    result = with_token(verify_customer)
    assert result == {"success": True, "verified": True}


def test_live_get_customer_accounts_and_account_isolation_contract() -> None:
    from rubies_agent.tools.account_tools import get_customer_accounts

    result = with_token(get_customer_accounts)
    assert result.get("success") is True, result
    data = result.get("data")
    assert isinstance(data, dict), result
    accounts = data.get("accounts")
    assert isinstance(accounts, list), result
    assert data.get("count") == len(accounts), result
    for account in accounts:
        assert account.get("account_reference")
        assert account.get("status") == "ACTIVE"
        assert account.get("currency")
    # The API must scope this result to the authenticated customer. The test
    # never supplies a customer ID; it can only request /api/accounts/me.


def _first_account_reference() -> str:
    from rubies_agent.tools.account_tools import get_customer_accounts

    result = with_token(get_customer_accounts)
    assert result.get("success") is True, result
    accounts = result["data"]["accounts"]
    if not accounts:
        pytest.skip("The E2E test customer has no active accounts.")
    return accounts[0]["account_reference"]


def test_live_get_balance_for_authenticated_customer() -> None:
    from rubies_agent.tools.account_tools import get_balance

    account_reference = _first_account_reference()
    result = with_token(lambda: get_balance(account_reference))
    assert_success_or_documented_domain_result(result)
    assert result.get("success") is True, result
    assert isinstance(result.get("data"), dict), result


def test_live_get_mini_statement_and_pagination() -> None:
    from rubies_agent.tools.account_tools import get_mini_statement

    account_reference = _first_account_reference()
    result = with_token(lambda: get_mini_statement(account_reference, limit=5, offset=0))
    assert_success_or_documented_domain_result(result)
    assert result.get("success") is True, result
    assert isinstance(result.get("data"), dict), result


def test_live_mini_statement_rejects_invalid_pagination_before_api_call() -> None:
    from rubies_agent.tools.account_tools import get_mini_statement

    result = run(get_mini_statement("ACC-DOES-NOT-MATTER", limit=0, offset=0))
    assert result.get("success") is False
    assert "limit 1-50" in result.get("error", "")


def test_live_get_transaction_status() -> None:
    reference = os.getenv("E2E_TRANSACTION_REFERENCE", "").strip()
    if not reference:
        pytest.skip("Set E2E_TRANSACTION_REFERENCE to a transaction owned by the test customer.")
    from rubies_agent.tools.transaction_tools import get_transaction_status

    result = with_token(lambda: get_transaction_status(reference))
    assert_success_or_documented_domain_result(result)
    assert result.get("success") is True, result


def test_live_get_loan_status() -> None:
    reference = os.getenv("E2E_LOAN_REFERENCE", "").strip()
    if not reference:
        pytest.skip("Set E2E_LOAN_REFERENCE to a loan owned by the test customer.")
    from rubies_agent.tools.loan_tools import get_loan_status

    result = with_token(lambda: get_loan_status(reference))
    assert_success_or_documented_domain_result(result)
    assert result.get("success") is True, result


def test_loan_eligibility_fails_closed_without_authoritative_endpoint() -> None:
    from rubies_agent.tools.loan_tools import check_loan_eligibility

    result = with_token(check_loan_eligibility)
    assert result.get("success") is False
    assert result.get("status") == "ASSESSMENT_UNAVAILABLE"
    assert "not a lending decision" in result.get("message", "")


def test_live_confirmation_creation_for_card_block() -> None:
    from rubies_agent.tools.confirmation_tools import create_confirmation

    # Creating a pending confirmation does not itself block the card.
    # Use a real test card reference explicitly configured by the operator.
    card_reference = os.getenv("E2E_CARD_REFERENCE", "").strip()
    if not card_reference:
        pytest.skip("Set E2E_CARD_REFERENCE to a card in the E2E test environment.")
    result = with_token(
        lambda: create_confirmation(
            action="BLOCK_CARD",
            payload={"card_reference": card_reference},
        )
    )
    assert_success_or_documented_domain_result(result)
    assert result.get("success") is True, result
    data = result.get("data", result)
    assert data.get("confirmation_id") or data.get("id"), result
    assert str(data.get("status", "PENDING")).upper() == "PENDING", result


def test_live_confirmation_create_then_approve_without_executing_action() -> None:
    """Exercise the real confirmation lifecycle without blocking a card."""
    from rubies_agent.tools.confirmation_tools import (
        approve_confirmation,
        create_confirmation,
    )

    card_reference = os.getenv("E2E_CARD_REFERENCE", "").strip()
    if not card_reference:
        pytest.skip("Set E2E_CARD_REFERENCE to a card in the E2E test environment.")

    created = with_token(
        lambda: create_confirmation(
            action="BLOCK_CARD",
            payload={"card_reference": card_reference},
        )
    )
    assert created.get("success") is True, created
    confirmation_id = created.get("data", {}).get("confirmation_id")
    assert confirmation_id, created

    approved = with_token(
        lambda: approve_confirmation(
            confirmation_id=confirmation_id,
            action="BLOCK_CARD",
            payload={"card_reference": card_reference},
        )
    )
    assert approved.get("success") is True, approved
    assert approved.get("data", {}).get("confirmation_id") == confirmation_id
    assert approved.get("data", {}).get("status") == "APPROVED"


def test_live_card_block_requires_explicit_opt_in() -> None:
    if os.getenv("E2E_ALLOW_CARD_BLOCK") != "1":
        pytest.skip(
            "Destructive scenario: set E2E_ALLOW_CARD_BLOCK=1 only in an isolated test environment."
        )
    card_reference = os.getenv("E2E_CARD_REFERENCE", "").strip()
    confirmation_id = os.getenv("E2E_APPROVED_CARD_CONFIRMATION_ID", "").strip()
    if not card_reference or not confirmation_id:
        pytest.skip(
            "Set E2E_CARD_REFERENCE and E2E_APPROVED_CARD_CONFIRMATION_ID "
            "after an explicit approval flow."
        )
    from rubies_agent.tools.card_tools import block_card

    result = with_token(lambda: block_card(card_reference, confirmation_id))
    assert result.get("success") is True, result
    data = result.get("data", {})
    assert data.get("card_reference") == card_reference
    assert data.get("status") == "BLOCKED"


def test_live_dispute_create_requires_explicit_opt_in() -> None:
    if os.getenv("E2E_ALLOW_DISPUTE_CREATE") != "1":
        pytest.skip(
            "Creates a persistent dispute: set E2E_ALLOW_DISPUTE_CREATE=1 "
            "only in an isolated test environment."
        )
    confirmation_id = os.getenv("E2E_APPROVED_DISPUTE_CONFIRMATION_ID", "").strip()
    if not confirmation_id:
        pytest.skip("Set E2E_APPROVED_DISPUTE_CONFIRMATION_ID from a completed confirmation flow.")
    from rubies_agent.tools.dispute_tools import open_dispute

    transaction_reference = os.getenv("E2E_DISPUTE_TRANSACTION_REFERENCE", "").strip()
    result = with_token(
        lambda: open_dispute(
            confirmation_id=confirmation_id,
            category="UNRECOGNIZED_TRANSACTION",
            description="Automated E2E test dispute; safe to close.",
            transaction_reference=transaction_reference or None,
        )
    )
    assert_success_or_documented_domain_result(result)
    assert result.get("success") is True, result


def test_live_support_handoff_requires_explicit_opt_in() -> None:
    if os.getenv("E2E_ALLOW_SUPPORT_HANDOFF") != "1":
        pytest.skip(
            "Creates a real support queue item: set E2E_ALLOW_SUPPORT_HANDOFF=1 "
            "in an isolated test environment."
        )
    from rubies_agent.tools.support_tools import handoff_to_human

    result = with_token(
        lambda: handoff_to_human(
            reason="Automated end-to-end test",
            summary="E2E support handoff validation; close this test ticket.",
            route="GENERAL_HUMAN_SUPPORT",
            priority="P4",
        )
    )
    assert result.get("success") is True, result
    data = result.get("data", {})
    assert data.get("reference")
    assert data.get("status")
    assert "awaiting human acknowledgement" in result.get("message", "").lower()


def test_handoff_rejects_blank_reason_without_calling_backend() -> None:
    from rubies_agent.tools.support_tools import handoff_to_human

    result = run(handoff_to_human(reason=" ", summary=" "))
    assert result.get("success") is False
    assert result.get("error") == "A reason and concise summary are required."


def test_confirmation_tools_reject_unsupported_action() -> None:
    from rubies_agent.tools.confirmation_tools import create_confirmation

    result = run(create_confirmation(action="TRANSFER_FUNDS", payload={}))
    assert result.get("success") is False
    assert result.get("error") == "Unsupported confirmation action."


def test_confirmation_approval_rejects_missing_id() -> None:
    from rubies_agent.tools.confirmation_tools import approve_confirmation

    result = run(
        approve_confirmation(
            confirmation_id=" ",
            action="BLOCK_CARD",
            payload={"card_reference": "CARD-001"},
        )
    )
    assert result.get("success") is False
    assert result.get("error") == "Confirmation ID is required."


def test_dispute_tool_rejects_missing_required_fields() -> None:
    from rubies_agent.tools.dispute_tools import open_dispute

    result = run(
        open_dispute(
            confirmation_id=" ",
            category="",
            description="",
        )
    )
    assert result.get("success") is False
    assert "confirmation, category, and description" in result.get("error", "")


def test_card_block_rejects_missing_confirmation() -> None:
    from rubies_agent.tools.card_tools import block_card

    result = run(block_card(card_reference="CARD-001", confirmation_id=" "))
    assert result.get("success") is False
    assert "confirmation" in result.get("error", "").lower()


def test_live_invalid_token_is_rejected_by_authoritative_api() -> None:
    from rubies_agent.request_context import (
        reset_request_access_token,
        set_request_access_token,
    )
    from rubies_agent.tools.identity_tools import verify_customer

    token_context = set_request_access_token("definitely-not-a-valid-bearer-token")
    try:
        result = run(verify_customer())
    finally:
        reset_request_access_token(token_context)

    assert result.get("success") is False, result
    assert result.get("verified") is False or result.get("status") == "BANKING_OPERATION_FAILED", (
        result
    )


def test_live_account_ownership_is_enforced_across_customers() -> None:
    other_customer_token = os.getenv("E2E_OTHER_CUSTOMER_ACCESS_TOKEN", "").strip()
    if not other_customer_token:
        pytest.skip("Set E2E_OTHER_CUSTOMER_ACCESS_TOKEN for cross-customer isolation coverage.")

    from rubies_agent.request_context import (
        reset_request_access_token,
        set_request_access_token,
    )
    from rubies_agent.tools.account_tools import get_balance

    account_reference = _first_account_reference()
    token_context = set_request_access_token(other_customer_token)
    try:
        result = run(get_balance(account_reference))
    finally:
        reset_request_access_token(token_context)

    assert result.get("success") is False, (
        f"Cross-customer account access unexpectedly succeeded. Returned result: {result!r}"
    )


def test_live_policy_search_returns_a_structured_result() -> None:
    from rubies_agent.tools.policy_tools import search_banking_policy

    result = search_banking_policy("What should a customer do about a failed transfer?")
    assert isinstance(result, dict), result
    # Retrieval corpus may have no match in a fresh checkout; shape must remain structured.
    assert "success" in result or "results" in result or "sources" in result or "error" in result
