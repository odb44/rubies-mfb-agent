"""HTTP endpoints for customer approval of sensitive banking actions."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from rubies_security.confirmations import ConfirmationError, ConfirmationExpiredError
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.services.confirmation_payload import (
    normalize_confirmation_payload,
)
from rubies_banking_api.services.confirmation_service import ConfirmationService

router = APIRouter(prefix="/api/confirmations", tags=["Confirmations"])

ALLOWED_ACTIONS = {"BLOCK_CARD", "OPEN_DISPUTE"}


class CreateConfirmationRequest(BaseModel):
    action: str = Field(min_length=1, max_length=50)
    payload: dict[str, str]


class CreateConfirmationResponse(BaseModel):
    confirmation_id: str
    action: str
    status: str
    expires_at: datetime


class ApproveConfirmationRequest(BaseModel):
    confirmation_id: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=50)
    payload: dict[str, str]


class ApproveConfirmationResponse(BaseModel):
    confirmation_id: str
    action: str
    status: str


def get_confirmation_service(db: Session) -> ConfirmationService:
    return ConfirmationService(ConfirmationRepository(db))


def _normalize_request_payload(
    action: str,
    payload: dict[str, str],
) -> dict:
    """Normalize action-specific payloads at the HTTP boundary."""
    try:
        return normalize_confirmation_payload(action, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("", response_model=CreateConfirmationResponse)
def create_confirmation(
    request: CreateConfirmationRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
) -> CreateConfirmationResponse:
    """Create a pending confirmation for an authenticated customer."""
    action = request.action.strip().upper()

    if action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This action cannot be confirmed through this endpoint.",
        )

    if action == "BLOCK_CARD" and not request.payload.get("card_reference", "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A card reference is required.",
        )

    payload = _normalize_request_payload(action, request.payload)
    service = get_confirmation_service(db)

    try:
        confirmation = service.create(
            identity,
            action=action,
            payload=payload,
            now=datetime.now(UTC),
        )
        db.commit()

        return CreateConfirmationResponse(
            confirmation_id=confirmation.confirmation_id,
            action=confirmation.action,
            status=confirmation.status,
            expires_at=confirmation.expires_at,
        )
    except IdentityVerificationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified customer identity is required.",
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/approve", response_model=ApproveConfirmationResponse)
def approve_confirmation(
    request: ApproveConfirmationRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
) -> ApproveConfirmationResponse:
    """Approve a pending confirmation for the authenticated customer."""
    action = request.action.strip().upper()

    if action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This action cannot be confirmed through this endpoint.",
        )

    if action == "BLOCK_CARD" and not request.payload.get("card_reference", "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A card reference is required.",
        )

    payload = _normalize_request_payload(action, request.payload)
    service = get_confirmation_service(db)

    try:
        confirmation = service.approve(
            identity,
            confirmation_id=request.confirmation_id,
            action=action,
            payload=payload,
            now=datetime.now(UTC),
        )
        db.commit()

        return ApproveConfirmationResponse(
            confirmation_id=confirmation.confirmation_id,
            action=confirmation.action,
            status=confirmation.status,
        )
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
            detail="This confirmation is not available to the authenticated customer.",
        ) from exc
    except ConfirmationExpiredError as exc:
        # Persist the repository's EXPIRED state transition before returning.
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This confirmation has expired. Create a new confirmation to continue.",
        ) from exc
    except ConfirmationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise