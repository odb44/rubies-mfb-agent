"""Single registry of tools exposed to the Strands agent."""

from rubies_agent.tools.account_tools import (
    get_balance,
    get_customer_accounts,
    get_mini_statement,
)
from rubies_agent.tools.card_tools import block_card, get_customer_cards
from rubies_agent.tools.confirmation_tools import (
    approve_confirmation,
    create_confirmation,
)
from rubies_agent.tools.dispute_tools import open_dispute
from rubies_agent.tools.identity_tools import verify_customer
from rubies_agent.tools.loan_tools import (
    assess_loan_delinquency_risk,
    check_loan_eligibility,
    get_loan_status,
)
from rubies_agent.tools.policy_tools import search_banking_policy
from rubies_agent.tools.support_tools import handoff_to_human
from rubies_agent.tools.transaction_tools import get_transaction_status

REGISTERED_TOOLS = (
    search_banking_policy,
    verify_customer,
    get_customer_accounts,
    get_balance,
    get_mini_statement,
    get_transaction_status,
    open_dispute,
    get_customer_cards,
    block_card,
    check_loan_eligibility,
    get_loan_status,
    assess_loan_delinquency_risk,
    handoff_to_human,
    create_confirmation,
    approve_confirmation,
)


def get_registered_tools() -> list:
    """Return a fresh list of the explicitly approved tools."""

    return list(REGISTERED_TOOLS)
