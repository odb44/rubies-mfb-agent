"""Database-backed confirmation storage and consumption."""

from datetime import UTC, datetime

from rubies_security.confirmations import (
    ConfirmationAlreadyConsumedError,
    ConfirmationExpiredError,
    ConfirmationRequiredError,
)
from rubies_security.identity import CustomerMismatchError, require_verified_identity
from rubies_shared.identity import CustomerIdentity
from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.confirmation import Confirmation


class ConfirmationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, confirmation: Confirmation) -> Confirmation:
        self.db.add(confirmation)
        self.db.flush()
        return confirmation

    def get_by_reference(self, confirmation_id: str) -> Confirmation | None:
        statement = select(Confirmation).where(
            Confirmation.confirmation_id == confirmation_id
        )
        return self.db.scalar(statement)

    def approve(
        self,
        *,
        confirmation_id: str,
        identity: CustomerIdentity,
        action: str,
        payload_hash: str,
        now: datetime | None = None,
    ) -> Confirmation:
        """Approve a pending confirmation belonging to this customer and session."""
        require_verified_identity(identity)
        current_time = now or datetime.now(UTC)

        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        statement = (
            select(Confirmation)
            .where(Confirmation.confirmation_id == confirmation_id)
            .with_for_update()
        )
        record = self.db.scalar(statement)

        if record is None:
            raise ConfirmationRequiredError("A valid confirmation is required.")

        if (
            record.customer_id != identity.customer_id
            or record.session_id != identity.session_id
        ):
            raise CustomerMismatchError(
                "Confirmation does not belong to this customer session."
            )

        if record.action != action or record.payload_hash != payload_hash:
            raise ConfirmationRequiredError(
                "Confirmation does not authorize this action."
            )

        if record.status == "CONSUMED":
            raise ConfirmationAlreadyConsumedError(
                "Confirmation has already been used."
            )

        if record.status != "PENDING":
            raise ConfirmationRequiredError(
                "Confirmation is not awaiting approval."
            )

        if current_time >= record.expires_at:
            record.status = "EXPIRED"
            self.db.flush()
            raise ConfirmationExpiredError("Confirmation has expired.")

        record.status = "APPROVED"
        record.approved_at = current_time
        self.db.flush()
        return record

    def consume(
        self,
        *,
        confirmation_id: str,
        identity: CustomerIdentity,
        action: str,
        payload_hash: str,
        now: datetime | None = None,
    ) -> Confirmation:
        """Lock, validate, and consume an approved confirmation."""
        require_verified_identity(identity)
        current_time = now or datetime.now(UTC)

        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        statement = (
            select(Confirmation)
            .where(Confirmation.confirmation_id == confirmation_id)
            .with_for_update()
        )
        record = self.db.scalar(statement)

        if record is None:
            raise ConfirmationRequiredError("A valid confirmation is required.")

        if (
            record.customer_id != identity.customer_id
            or record.session_id != identity.session_id
        ):
            raise CustomerMismatchError(
                "Confirmation does not belong to this customer session."
            )

        if record.action != action or record.payload_hash != payload_hash:
            raise ConfirmationRequiredError(
                "Confirmation does not authorize this action."
            )

        if record.status == "CONSUMED":
            raise ConfirmationAlreadyConsumedError(
                "Confirmation has already been used."
            )

        if record.status != "APPROVED":
            raise ConfirmationRequiredError(
                "Confirmation has not been approved."
            )

        if current_time >= record.expires_at:
            record.status = "EXPIRED"
            self.db.flush()
            raise ConfirmationExpiredError("Confirmation has expired.")

        record.status = "CONSUMED"
        record.consumed_at = current_time
        self.db.flush()
        return record