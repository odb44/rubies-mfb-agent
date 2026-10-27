"""Business logic for customer approval of sensitive banking actions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from rubies_security.identity import require_verified_identity
from rubies_shared.confirmations import ConfirmationStatus
from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.models.confirmation import Confirmation
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.services.confirmation_payload import (
    hash_confirmation_payload,
)

CONFIRMATION_TTL = timedelta(minutes=5)


class ConfirmationService:
    """Coordinates creation and approval of action-bound confirmations."""

    def __init__(
        self,
        confirmation_repository: ConfirmationRepository,
    ) -> None:
        self.confirmation_repository = confirmation_repository

    def create(
        self,
        identity: CustomerIdentity,
        *,
        action: str,
        payload: dict,
        now: datetime | None = None,
    ) -> Confirmation:
        """Create a pending confirmation bound to an action and its payload."""
        verified_identity = require_verified_identity(identity)

        normalized_action = action.strip().upper()
        if not normalized_action:
            raise ValueError("An action is required.")

        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        confirmation = Confirmation(
            confirmation_id=f"CONF-{uuid4().hex}",
            customer_id=verified_identity.customer_id,
            session_id=verified_identity.session_id,
            action=normalized_action,
            payload_hash=hash_confirmation_payload(payload),
            status=ConfirmationStatus.PENDING.value,
            created_at=current_time,
            expires_at=current_time + CONFIRMATION_TTL,
        )

        return self.confirmation_repository.add(confirmation)

    def approve(
        self,
        identity: CustomerIdentity,
        *,
        confirmation_id: str,
        action: str,
        payload: dict,
        now: datetime | None = None,
    ) -> Confirmation:
        """Approve a pending confirmation for its exact action payload."""
        verified_identity = require_verified_identity(identity)

        normalized_action = action.strip().upper()
        if not normalized_action:
            raise ValueError("An action is required.")

        return self.confirmation_repository.approve(
            confirmation_id=confirmation_id,
            identity=verified_identity,
            action=normalized_action,
            payload_hash=hash_confirmation_payload(payload),
            now=now,
        )