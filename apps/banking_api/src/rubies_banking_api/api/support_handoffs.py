"""Customer-facing support handoff endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.schemas.support_handoff import (
    SupportHandoffCreate,
    SupportHandoffResponse,
)
from rubies_banking_api.services.support_handoff_service import (
    SupportHandoffService,
)

router = APIRouter(
    prefix="/api/support-handoffs",
    tags=["Support Handoffs"],
)


def _build_service(db: Session) -> SupportHandoffService:
    return SupportHandoffService(db)


@router.post(
    "",
    response_model=SupportHandoffResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_support_handoff(
    payload: SupportHandoffCreate,
    db: Session = Depends(get_db),
    identity=Depends(get_customer_identity),
) -> SupportHandoffResponse:
    """Create a support request for the authenticated customer."""
    service = _build_service(db)

    try:
        handoff = service.create(
            identity=identity,
            reason=payload.reason,
            summary=payload.summary,
            route=payload.route.value,
            priority=payload.priority.value,
            actions_attempted=payload.actions_attempted,
            unresolved_questions=payload.unresolved_questions,
            correlation_id=payload.correlation_id,
        )
        db.commit()
        db.refresh(handoff)
        return SupportHandoffResponse.model_validate(handoff)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.get(
    "",
    response_model=list[SupportHandoffResponse],
)
def list_support_handoffs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    identity=Depends(get_customer_identity),
) -> list[SupportHandoffResponse]:
    """List support requests belonging to the authenticated customer."""
    service = _build_service(db)

    try:
        handoffs = service.list_for_customer(
            identity=identity,
            limit=limit,
        )
        return [
            SupportHandoffResponse.model_validate(handoff)
            for handoff in handoffs
        ]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.get(
    "/{reference}",
    response_model=SupportHandoffResponse,
)
def get_support_handoff(
    reference: str,
    db: Session = Depends(get_db),
    identity=Depends(get_customer_identity),
) -> SupportHandoffResponse:
    """Retrieve a support request belonging to the authenticated customer."""
    service = _build_service(db)

    try:
        handoff = service.get_for_customer(
            identity=identity,
            reference=reference,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support handoff not found.",
        )

    return SupportHandoffResponse.model_validate(handoff)