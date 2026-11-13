"""Repository for read-only loan application enquiries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.loan_application import LoanApplication


class LoanApplicationRepository:
    """Read-only queries for loan applications."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_reference(
        self,
        application_reference: str,
    ) -> LoanApplication | None:
        """Retrieve a loan application by its unique reference."""
        statement = select(LoanApplication).where(
            LoanApplication.application_reference == application_reference
        )
        return self.db.scalar(statement)

    def list_by_customer(
        self,
        customer_id: int,
    ) -> list[LoanApplication]:
        """Retrieve all loan applications belonging to a customer."""
        statement = (
            select(LoanApplication)
            .where(LoanApplication.customer_id == customer_id)
            .order_by(
                LoanApplication.applied_at.desc(),
                LoanApplication.id.desc(),
            )
        )
        return list(self.db.scalars(statement).all())
