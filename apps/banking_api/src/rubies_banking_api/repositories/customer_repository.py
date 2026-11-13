from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.customer import Customer


class CustomerRepository:
    """Handles database access for customer records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_reference(self, customer_reference: str) -> Customer | None:
        """Find a customer by their unique banking reference."""
        statement = select(Customer).where(Customer.customer_reference == customer_reference)
        return self.db.scalar(statement)
