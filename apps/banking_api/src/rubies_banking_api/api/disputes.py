"""HTTP endpoints for customer dispute operations."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from rubies_security.confirmations import (
    ConfirmationAlreadyConsumedError,
    ConfirmationExpiredError,
    ConfirmationRequiredError,
)
from rubies_security.identity import CustomerMismatchError, IdentityVerificationError
from rubies_shared.identity import CustomerIdentity
from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.models.dispute import Dispute
from rubies_banking_api.models.transaction import Transaction
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.repositories.dispute_repository import DisputeRepository
from rubies_banking_api.services.dispute_service import DisputeService

router = APIRouter(prefix="/api/disputes", tags=["Disputes"])


class CreateDisputeRequest(BaseModel):
    """Customer's request to open a dispute."""

    confirmation_id: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=5000)
    transaction_reference: str | None = Field(default=None, max_length=50)


class DisputeResponse(BaseModel):
    """Customer-facing dispute details."""

    case_reference: str
    category: str
    description: str
    status: str
    transaction_reference: str | None
    created_at: str


class DisputeListResponse(BaseModel):
    """Paginated list of the authenticated customer's disputes."""

    items: list[DisputeResponse]
    limit: int
    offset: int


def _build_service(db: Session) -> DisputeService:
    """Build the dispute service with request-scoped repositories."""
    return DisputeService(
        dispute_repository=DisputeRepository(db),
        customer_repository=CustomerRepository(db),
        confirmation_repository=ConfirmationRepository(db),
        audit_repository=AuditRepository(db),
    )


def _to_response(dispute: Dispute) -> DisputeResponse:
    transaction_reference = (
        dispute.transaction.reference if dispute.transaction is not None else None
    )

    return DisputeResponse(
        case_reference=dispute.case_reference,
        category=dispute.category,
        description=dispute.description,
        status=dispute.status,
        transaction_reference=transaction_reference,
        created_at=dispute.created_at.isoformat(),
    )


@router.post(
    "",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dispute(
    request: CreateDisputeRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
) -> DisputeResponse:
    """Open a dispute after validating its approved confirmation."""
    correlation_id = f"CORR-{uuid4().hex}"
    service = _build_service(db)

    try:
        transaction = None

        if request.transaction_reference is not None:
            transaction_reference = request.transaction_reference.strip()

            if not transaction_reference:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Transaction reference must not be blank.",
                )

            transaction = db.scalar(
                select(Transaction).where(
                    Transaction.reference == transaction_reference
                )
            )

            if transaction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Transaction not found.",
                )

        dispute = service.create_dispute(
            identity,
            confirmation_id=request.confirmation_id,
            category=request.category,
            description=request.description,
            correlation_id=correlation_id,
            transaction=transaction,
        )
        db.commit()
        db.refresh(dispute)

        return _to_response(dispute)

    except HTTPException:
        db.rollback()
        raise

    except IdentityVerificationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified customer identity is required.",
        ) from exc

    except CustomerMismatchError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The requested resource is not available to this customer.",
        ) from exc

    except ConfirmationAlreadyConsumedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This confirmation has already been used.",
        ) from exc

    except ConfirmationExpiredError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This confirmation has expired.",
        ) from exc

    except ConfirmationRequiredError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A valid approved confirmation for this request is required.",
        ) from exc

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.get("", response_model=DisputeListResponse)
def list_disputes(
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DisputeListResponse:
    """List disputes belonging only to the authenticated customer."""
    service = _build_service(db)

    try:
        customer = service.resolve_customer(identity)
        disputes = DisputeRepository(db).list_by_customer(
            customer.id,
            limit=limit,
            offset=offset,
        )

        return DisputeListResponse(
            items=[_to_response(dispute) for dispute in disputes],
            limit=limit,
            offset=offset,
        )

    except IdentityVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified customer identity is required.",
        ) from exc

    except CustomerMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The customer account is not available.",
        ) from exc