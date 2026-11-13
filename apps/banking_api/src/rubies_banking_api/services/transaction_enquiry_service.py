"""Business rules for read-only transaction enquiries."""

from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.repositories.customer_repository import (
    CustomerRepository,
)
from rubies_banking_api.repositories.transaction_repository import (
    TransactionRepository,
)


class TransactionEnquiryService:
    """Enforce customer identity and ownership for enquiries."""

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        customer_repository: CustomerRepository,
    ) -> None:
        self.transaction_repository = transaction_repository
        self.customer_repository = customer_repository

    def _resolve_customer(self, identity: CustomerIdentity):
        if not identity.verified:
            raise IdentityVerificationError("A verified customer identity is required.")

        customer = self.customer_repository.get_by_reference(identity.customer_id)

        if customer is None or not customer.is_active:
            raise CustomerMismatchError("The customer account is not available.")

        return customer

    def get_mini_statement(
        self,
        identity: CustomerIdentity,
        *,
        account_reference: str,
        limit: int = 10,
        offset: int = 0,
    ):
        customer = self._resolve_customer(identity)

        account = self.transaction_repository.get_account_by_number(account_reference)

        if account is None:
            raise ValueError("Account not found.")

        if account.customer_id != customer.id:
            raise CustomerMismatchError("The requested account is not available to this customer.")

        if account.status != "ACTIVE":
            raise ValueError("This account is not active.")

        transactions = self.transaction_repository.list_by_account(
            account.id,
            limit=limit,
            offset=offset,
        )
        return account, transactions

    def get_transaction_status(
        self,
        identity: CustomerIdentity,
        *,
        transaction_reference: str,
    ):
        customer = self._resolve_customer(identity)

        transaction = self.transaction_repository.get_by_reference(transaction_reference)

        if transaction is None:
            raise ValueError("Transaction not found.")

        if transaction.account.customer_id != customer.id:
            raise CustomerMismatchError(
                "The requested transaction is not available to this customer."
            )

        return transaction
