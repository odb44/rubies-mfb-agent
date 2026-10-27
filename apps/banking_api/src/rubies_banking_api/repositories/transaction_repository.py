"""Repository for account and transaction enquiry queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.account import Account
from rubies_banking_api.models.transaction import Transaction


class TransactionRepository:
    """Read-only queries used by transaction enquiry services."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_account_by_number(self, account_number: str) -> Account | None:
        statement = select(Account).where(
            Account.account_number == account_number
        )
        return self.db.scalar(statement)

    def get_by_reference(self, reference: str) -> Transaction | None:
        statement = select(Transaction).where(
            Transaction.reference == reference
        )
        return self.db.scalar(statement)

    def list_by_account(
        self,
        account_id: int,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Transaction]:
        statement = (
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(
                Transaction.created_at.desc(),
                Transaction.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())