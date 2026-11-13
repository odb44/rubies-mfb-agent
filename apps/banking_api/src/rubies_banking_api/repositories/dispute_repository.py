
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from rubies_banking_api.models.dispute import Dispute


class DisputeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, dispute_id: int) -> Dispute | None:
        statement = select(Dispute).where(Dispute.id == dispute_id)
        return self.db.scalar(statement)

    def get_by_case_reference(self, case_reference: str) -> Dispute | None:
        statement = select(Dispute).where(
            Dispute.case_reference == case_reference
        )
        return self.db.scalar(statement)

    def list_by_customer(
        self,
        customer_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Dispute]:
        statement = (
            select(Dispute)
            .where(Dispute.customer_id == customer_id)
            .order_by(Dispute.created_at.desc(), Dispute.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def list_all(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Dispute]:
        """List all disputes for the staff support desk, newest first."""
        statement = (
            select(Dispute)
            .options(joinedload(Dispute.customer))
            .order_by(Dispute.created_at.desc(), Dispute.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def add(self, dispute: Dispute) -> Dispute:
        self.db.add(dispute)
        return dispute

    def save(self, dispute: Dispute) -> Dispute:
        self.db.add(dispute)
        self.db.flush()
        self.db.refresh(dispute)
        return dispute


