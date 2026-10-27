"""Business logic for security-sensitive card operations."""

from datetime import UTC, datetime
from uuid import uuid4

from rubies_security.identity import (
    CustomerMismatchError,
    require_customer_match,
    require_verified_identity,
)
from rubies_shared.audit import AuditEvent
from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.models.card import Card
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.card_repository import CardRepository
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.services.confirmation_payload import (
    hash_confirmation_payload,
)


class CardService:
    """Coordinates card validation, blocking, and audit logging."""

    def __init__(
        self,
        card_repository: CardRepository,
        customer_repository: CustomerRepository,
        confirmation_repository: ConfirmationRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.card_repository = card_repository
        self.customer_repository = customer_repository
        self.confirmation_repository = confirmation_repository
        self.audit_repository = audit_repository

    def block_card(
        self,
        identity: CustomerIdentity,
        *,
        card_reference: str,
        confirmation_id: str,
        correlation_id: str,
        now: datetime | None = None,
    ) -> Card:
        """Block an owned active card using an approved confirmation."""
        verified_identity = require_verified_identity(identity)

        normalized_reference = card_reference.strip()
        if not normalized_reference:
            raise ValueError("A card reference is required.")

        if not correlation_id.strip():
            raise ValueError("A correlation ID is required.")

        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        db = self.card_repository.db

        try:
            customer = self.customer_repository.get_by_reference(
                verified_identity.customer_id
            )

            if customer is None:
                raise CustomerMismatchError(
                    "The verified customer could not be found."
                )

            require_customer_match(
                verified_identity,
                customer.customer_reference,
            )

            if not customer.is_active:
                raise CustomerMismatchError(
                    "The customer account is not active."
                )

            card = self.card_repository.get_by_reference_for_update(
                normalized_reference
            )

            if card is None:
                raise ValueError("The requested card could not be found.")

            if card.customer_id != customer.id:
                raise CustomerMismatchError(
                    "The card does not belong to this customer."
                )

            

            payload = {"card_reference": normalized_reference}
            payload_hash = hash_confirmation_payload(payload)

            self.confirmation_repository.consume(
                confirmation_id=confirmation_id,
                identity=verified_identity,
                action="BLOCK_CARD",
                payload_hash=payload_hash,
                now=current_time,
            )
            if card.status != "ACTIVE":
                raise ValueError(
                    f"This card cannot be blocked because its status is {card.status}."
                )
            card.status = "BLOCKED"
            self.card_repository.save(card)

            self.audit_repository.record(
                AuditEvent(
                    event_id=f"AUD-{uuid4().hex}",
                    occurred_at=current_time,
                    actor_id=verified_identity.customer_id,
                    action="BLOCK_CARD",
                    outcome="SUCCESS",
                    correlation_id=correlation_id,
                    details={
                        "card_reference": card.card_reference,
                        "previous_status": "ACTIVE",
                        "new_status": "BLOCKED",
                    },
                )
            )

            return card

        except Exception:
            db.rollback()
            raise