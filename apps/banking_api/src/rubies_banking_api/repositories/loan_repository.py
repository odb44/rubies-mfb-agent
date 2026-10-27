"""Repository for read-only loan enquiries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.loan import Loan


class LoanRepository:
    """Read-only queries for customer loans."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_reference(self, loan_reference: str) -> Loan | None:
        """Retrieve a loan by its unique reference."""
        statement = select(Loan).where(
            Loan.loan_reference == loan_reference
        )
        return self.db.scalar(statement)

    def list_by_customer(self, customer_id: int) -> list[Loan]:
        """Retrieve all loans belonging to a customer."""
        statement = (
            select(Loan)
            .where(Loan.customer_id == customer_id)
            .order_by(Loan.disbursed_at.desc(), Loan.id.desc())
        )
        return list(self.db.scalars(statement).all())