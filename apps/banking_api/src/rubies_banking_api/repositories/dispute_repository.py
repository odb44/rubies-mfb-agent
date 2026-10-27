from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.dispute import Dispute


class DisputeRepository:
    """Handles database operations for dispute records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, dispute_id: int) -> Dispute | None:
        """Find a dispute by its internal database ID."""
        statement = select(Dispute).where(Dispute.id == dispute_id)
        return self.db.scalar(statement)

    def get_by_case_reference(self, case_reference: str) -> Dispute | None:
        """Find a dispute by its customer-facing case reference."""
        statement = select(Dispute).where(
            Dispute.case_reference == case_reference
        )
        return self.db.scalar(statement)

    def list_by_customer(
        self,
        customer_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Dispute]:
        """List a customer's disputes, newest first."""
        statement = (
            select(Dispute)
            .where(Dispute.customer_id == customer_id)
            .order_by(Dispute.created_at.desc(), Dispute.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def add(self, dispute: Dispute) -> Dispute:
        """Stage a dispute for insertion into the current transaction."""
        self.db.add(dispute)
        return dispute

    def save(self, dispute: Dispute) -> Dispute:
        """Persist changes to a dispute within the current transaction."""
        self.db.add(dispute)
        self.db.flush()
        return dispute
