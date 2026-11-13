"""Business logic for preparing customer dispute requests."""

from datetime import UTC, datetime
from uuid import uuid4

from rubies_security.identity import (
    CustomerMismatchError,
    require_customer_match,
    require_verified_identity,
)
from rubies_shared.audit import AuditEvent
from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.models.customer import Customer
from rubies_banking_api.models.dispute import Dispute
from rubies_banking_api.models.transaction import Transaction
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.repositories.dispute_repository import DisputeRepository
from rubies_banking_api.services.confirmation_payload import (
    hash_confirmation_payload,
    normalize_confirmation_payload,
)

DISPUTE_CATEGORIES = frozenset(
    {
        "TRANSFER_FAILED_DEBITED",
        "TRANSFER_DELAYED_OR_UNKNOWN",
        "DUPLICATE_DEBIT",
        "BENEFICIARY_NOT_CREDITED",
        "CARD_LOST_OR_STOLEN",
        "UNRECOGNIZED_TRANSACTION",
        "FEE_OR_CHARGE_QUERY",
        "ACCOUNT_ACCESS_OR_KYC",
        "LOAN_QUERY_OR_COMPLAINT",
        "SERVICE_OR_STAFF_COMPLAINT",
        "OTHER_OR_UNCLEAR",
    }
)


class DisputeService:
    """Coordinates dispute validation and database operations."""

    def __init__(
        self,
        dispute_repository: DisputeRepository,
        customer_repository: CustomerRepository,
        confirmation_repository: ConfirmationRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.dispute_repository = dispute_repository
        self.customer_repository = customer_repository
        self.confirmation_repository = confirmation_repository
        self.audit_repository = audit_repository

    def resolve_customer(
        self,
        identity: CustomerIdentity,
    ) -> Customer:
        """Resolve a verified customer reference to its database record."""
        verified_identity = require_verified_identity(identity)

        customer = self.customer_repository.get_by_reference(verified_identity.customer_id)

        if customer is None:
            raise CustomerMismatchError("The verified customer could not be found.")

        require_customer_match(
            verified_identity,
            customer.customer_reference,
        )

        if not customer.is_active:
            raise CustomerMismatchError("The customer account is not active.")

        return customer

    def validate_request(
        self,
        identity: CustomerIdentity,
        *,
        category: str,
        description: str,
        transaction: Transaction | None = None,
    ) -> Customer:
        """Validate a proposed dispute without creating a dispute record."""
        customer = self.resolve_customer(identity)

        normalized_category = category.strip().upper()

        if normalized_category not in DISPUTE_CATEGORIES:
            raise ValueError("Unsupported dispute category.")

        if not description.strip():
            raise ValueError("A dispute description is required.")

        if transaction is not None:
            if transaction.account.customer_id != customer.id:
                raise CustomerMismatchError("The transaction does not belong to this customer.")

        return customer

    def create_dispute(
        self,
        identity: CustomerIdentity,
        *,
        confirmation_id: str,
        category: str,
        description: str,
        correlation_id: str,
        transaction: Transaction | None = None,
        now: datetime | None = None,
    ) -> Dispute:
        """Create a dispute using an approved, single-use confirmation."""
        verified_identity = require_verified_identity(identity)

        normalized_category = category.strip().upper()
        normalized_description = description.strip()

        if not correlation_id.strip():
            raise ValueError("A correlation ID is required.")

        customer = self.validate_request(
            verified_identity,
            category=normalized_category,
            description=normalized_description,
            transaction=transaction,
        )

        confirmation_payload: dict[str, str] = {
            "category": normalized_category,
            "description": normalized_description,
        }

        if transaction is not None:
            confirmation_payload["transaction_reference"] = transaction.reference

        canonical_payload = normalize_confirmation_payload(
            "OPEN_DISPUTE",
            confirmation_payload,
        )
        payload_hash = hash_confirmation_payload(canonical_payload)

        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        case_reference = f"DIS-{uuid4().hex[:12].upper()}"

        try:
            self.confirmation_repository.consume(
                confirmation_id=confirmation_id,
                identity=verified_identity,
                action="OPEN_DISPUTE",
                payload_hash=payload_hash,
                now=current_time,
            )

            dispute = Dispute(
                case_reference=case_reference,
                customer_id=customer.id,
                transaction_id=(transaction.id if transaction is not None else None),
                category=normalized_category,
                description=normalized_description,
                status="OPEN",
            )
            self.dispute_repository.add(dispute)
            self.dispute_repository.db.flush()

            audit_event = AuditEvent(
                event_id=f"AUD-{uuid4().hex}",
                occurred_at=current_time,
                actor_id=verified_identity.customer_id,
                action="OPEN_DISPUTE",
                outcome="SUCCESS",
                correlation_id=correlation_id,
                details={
                    "case_reference": case_reference,
                    "category": normalized_category,
                    "transaction_id": (transaction.id if transaction is not None else None),
                },
            )
            self.audit_repository.record(audit_event)

            return dispute

        except Exception:
            self.dispute_repository.db.rollback()
            raise