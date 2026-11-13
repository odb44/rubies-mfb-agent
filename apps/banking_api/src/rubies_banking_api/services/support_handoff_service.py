"""Business logic for human support handoffs."""

from datetime import UTC, datetime

from rubies_security.identity import require_verified_identity
from sqlalchemy.orm import Session

from rubies_banking_api.models.support_handoff import (
    HandoffStatus,
    SupportHandoff,
)
from rubies_banking_api.repositories.customer_repository import (
    CustomerRepository,
)
from rubies_banking_api.repositories.support_handoff_repository import (
    SupportHandoffRepository,
)


class SupportHandoffService:
    """Create, retrieve, and manage customer support handoffs."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.handoffs = SupportHandoffRepository(db)

    def _get_active_customer(self, identity):
        """Return the verified customer's active database record."""
        require_verified_identity(identity)

        customer = self.customers.get_by_reference(identity.customer_id)

        if customer is None or not customer.is_active:
            raise ValueError("An active customer account is required.")

        return customer

    def create(
        self,
        *,
        identity,
        reason: str,
        summary: str,
        route: str,
        priority: str,
        actions_attempted: list[str],
        unresolved_questions: list[str],
        correlation_id: str | None,
    ) -> SupportHandoff:
        """Create a handoff awaiting explicit human acknowledgement."""
        customer = self._get_active_customer(identity)

        handoff = SupportHandoff(
            customer_id=customer.id,
            status=HandoffStatus.PENDING_ACKNOWLEDGEMENT.value,
            reason=reason,
            summary=summary,
            route=route,
            priority=priority,
            actions_attempted=actions_attempted,
            unresolved_questions=unresolved_questions,
            correlation_id=correlation_id,
        )

        try:
            return self.handoffs.add(handoff)
        except Exception:
            self.db.rollback()
            raise

    def get_for_customer(
        self,
        *,
        identity,
        reference: str,
    ) -> SupportHandoff | None:
        """Retrieve a handoff belonging to the verified customer."""
        customer = self._get_active_customer(identity)

        return self.handoffs.get_by_reference(
            reference=reference,
            customer_id=customer.id,
        )

    def list_for_customer(
        self,
        *,
        identity,
        limit: int = 20,
    ) -> list[SupportHandoff]:
        """List handoffs belonging to the verified customer."""
        customer = self._get_active_customer(identity)

        return self.handoffs.list_for_customer(
            customer_id=customer.id,
            limit=limit,
        )

    def acknowledge(
        self,
        *,
        reference: str,
        acknowledgement_reference: str,
    ) -> SupportHandoff:
        """Record explicit acknowledgement by a trusted support workflow.

        This is a service operation, not a customer-facing endpoint.
        The caller must enforce support-operator authentication and
        authorization before invoking it.
        """
        if not acknowledgement_reference.strip():
            raise ValueError("An acknowledgement reference is required.")

        handoff = self._get_handoff_for_transition(reference)

        if handoff.status != HandoffStatus.PENDING_ACKNOWLEDGEMENT.value:
            raise ValueError("Only pending handoffs can be acknowledged.")

        handoff.status = HandoffStatus.ACKNOWLEDGED.value
        handoff.acknowledgement_reference = acknowledgement_reference
        handoff.acknowledged_at = datetime.now(UTC)

        try:
            self.db.flush()
            return handoff
        except Exception:
            self.db.rollback()
            raise

    def mark_failed(
        self,
        *,
        reference: str,
        failure_reason: str,
    ) -> SupportHandoff:
        """Mark a pending handoff as failed in a trusted workflow."""
        if not failure_reason.strip():
            raise ValueError("A failure reason is required.")

        handoff = self._get_handoff_for_transition(reference)

        if handoff.status != HandoffStatus.PENDING_ACKNOWLEDGEMENT.value:
            raise ValueError("Only pending handoffs can be marked as failed.")

        handoff.status = HandoffStatus.FAILED.value
        handoff.failure_reason = failure_reason

        try:
            self.db.flush()
            return handoff
        except Exception:
            self.db.rollback()
            raise

    def _get_handoff_for_transition(
        self,
        reference: str,
    ) -> SupportHandoff:
        """Retrieve a handoff for a trusted internal transition."""
        handoff = (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.reference == reference)
            .with_for_update()
            .one_or_none()
        )

        if handoff is None:
            raise ValueError("Support handoff not found.")

        return handoff
