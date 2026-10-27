"""Explicit permission rules for customer-support operations."""

from enum import StrEnum

from rubies_shared import CustomerIdentity

from rubies_security.identity import (
    require_verified_identity,
)


class BankingAction(StrEnum):
    GET_BALANCE = "get_balance"
    GET_MINI_STATEMENT = "get_mini_statement"
    GET_TRANSACTION_STATUS = "get_transaction_status"
    OPEN_DISPUTE = "open_dispute"
    BLOCK_CARD = "block_card"
    CHECK_LOAN_ELIGIBILITY = "check_loan_eligibility"
    GET_LOAN_STATUS = "get_loan_status"
    HANDOFF_TO_HUMAN = "handoff_to_human"


CONFIRMATION_REQUIRED_ACTIONS = frozenset(
    {
        BankingAction.OPEN_DISPUTE,
        BankingAction.BLOCK_CARD,
    }
)


def require_allowed_action(
    identity: CustomerIdentity | None,
    action: BankingAction,
) -> None:
    """Require a verified identity and a recognized support action."""

    require_verified_identity(identity)

    if not isinstance(action, BankingAction):
        raise ValueError("Unrecognized banking action.")
