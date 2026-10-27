"""In-memory confirmation validation for development and unit tests."""

from dataclasses import dataclass
from datetime import UTC, datetime

from rubies_shared import ConfirmationRequest, ConfirmationStatus, CustomerIdentity

from rubies_security.identity import (
    CustomerMismatchError,
    SecurityError,
    require_verified_identity,
)


class ConfirmationError(SecurityError):
    """Base exception for confirmation failures."""


class ConfirmationRequiredError(ConfirmationError):
    """Raised when no valid approval is supplied."""


class ConfirmationExpiredError(ConfirmationError):
    """Raised when approval has expired."""


class ConfirmationAlreadyConsumedError(ConfirmationError):
    """Raised when approval has already been consumed."""


@dataclass(slots=True)
class _StoredConfirmation:
    request: ConfirmationRequest
    consumed: bool = False


class InMemoryConfirmationStore:
    """Development-only confirmation store; not safe for production concurrency."""

    def __init__(self) -> None:
        self._records: dict[str, _StoredConfirmation] = {}

    def add(self, request: ConfirmationRequest) -> None:
        if request.confirmation_id in self._records:
            raise ValueError("Confirmation ID already exists.")

        self._records[request.confirmation_id] = _StoredConfirmation(request=request)

    def consume(
        self,
        *,
        confirmation_id: str,
        identity: CustomerIdentity,
        action: str,
        now: datetime | None = None,
    ) -> ConfirmationRequest:
        """Validate and consume an approval in a single-process development store."""

        require_verified_identity(identity)

        stored = self._records.get(confirmation_id)
        if stored is None:
            raise ConfirmationRequiredError("A valid confirmation is required.")

        request = stored.request

        if request.customer_id != identity.customer_id:
            raise CustomerMismatchError("Confirmation belongs to another customer.")

        if request.action != action:
            raise ConfirmationRequiredError(
                "Confirmation does not authorize this action."
            )

        if stored.consumed or request.status == ConfirmationStatus.CONSUMED:
            raise ConfirmationAlreadyConsumedError("Confirmation has already been used.")

        if request.status != ConfirmationStatus.APPROVED:
            raise ConfirmationRequiredError("Confirmation has not been approved.")

        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        if current_time >= request.expires_at:
            raise ConfirmationExpiredError("Confirmation has expired.")

        stored.consumed = True
        return request
