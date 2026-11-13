"""Persistence operations for customer cards."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.card import Card


class CardRepository:
    """Provides database access to cards."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_reference(self, card_reference: str) -> Card | None:
        """Retrieve a card by its public reference."""
        statement = select(Card).where(Card.card_reference == card_reference)
        return self.db.scalar(statement)

    def get_by_reference_for_update(self, card_reference: str) -> Card | None:
        """Retrieve and lock a card for a state-changing operation."""
        statement = select(Card).where(Card.card_reference == card_reference).with_for_update()
        return self.db.scalar(statement)

    def save(self, card: Card) -> Card:
        """Stage card changes in the current transaction."""
        self.db.add(card)
        self.db.flush()
        return card

    def list_by_customer(self, customer_id: int) -> list[Card]:
        """Retrieve all cards belonging to a customer."""
        statement = (
            select(Card)
            .where(Card.customer_id == customer_id)
            .order_by(Card.created_at.desc(), Card.id.desc())
        )
        return list(self.db.scalars(statement).all())
