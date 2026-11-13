
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from rubies_banking_api.models.support_handoff import SupportHandoff


class SupportHandoffRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, handoff: SupportHandoff) -> SupportHandoff:
        self.db.add(handoff)
        return handoff

    def get_by_reference(
        self,
        reference: str,
        customer_id: int,
    ) -> SupportHandoff | None:
        statement = select(SupportHandoff).where(
            SupportHandoff.reference == reference,
            SupportHandoff.customer_id == customer_id,
        )
        return self.db.scalar(statement)

    def list_for_customer(
        self,
        customer_id: int,
        limit: int = 20,
    ) -> list[SupportHandoff]:
        statement = (
            select(SupportHandoff)
            .where(SupportHandoff.customer_id == customer_id)
            .order_by(
                SupportHandoff.created_at.desc(),
                SupportHandoff.id.desc(),
            )
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def list_all(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SupportHandoff]:
        """List all support handoffs for the staff support desk."""
        statement = (
            select(SupportHandoff)
            .options(joinedload(SupportHandoff.customer))
            .order_by(
                SupportHandoff.created_at.desc(),
                SupportHandoff.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())
