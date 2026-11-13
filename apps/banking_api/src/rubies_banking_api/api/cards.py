"""HTTP endpoints for customer card operations."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.card_repository import CardRepository
from rubies_banking_api.repositories.confirmation_repository import (
    ConfirmationRepository,
)
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.services.card_service import CardService

router = APIRouter(prefix="/api/cards", tags=["Cards"])


class BlockCardRequest(BaseModel):
    confirmation_id: str = Field(min_length=1, max_length=100)


class BlockCardResponse(BaseModel):
    card_reference: str
    status: str
    correlation_id: str

class CardListItem(BaseModel):
    card_reference: str
    masked_number: str
    card_type: str
    status: str


class CardListResponse(BaseModel):
    items: list[CardListItem]

@router.get("", response_model=CardListResponse)
def list_cards(
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
) -> CardListResponse:
    """List cards belonging only to the authenticated customer."""
    service = CardService(
        card_repository=CardRepository(db),
        customer_repository=CustomerRepository(db),
        confirmation_repository=ConfirmationRepository(db),
        audit_repository=AuditRepository(db),
    )

    try:
        cards = service.list_customer_cards(identity)

        return CardListResponse(
            items=[
                CardListItem(
                    card_reference=card.card_reference,
                    masked_number=card.masked_number,
                    card_type=card.card_type,
                    status=card.status,
                )
                for card in cards
            ]
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

@router.post(
    "/{card_reference}/block",
    response_model=BlockCardResponse,
)
def block_card(
    card_reference: str,
    request: BlockCardRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
) -> BlockCardResponse:
    """Block a customer's card after an approved confirmation."""
    correlation_id = f"CORR-{uuid4().hex}"

    service = CardService(
        card_repository=CardRepository(db),
        customer_repository=CustomerRepository(db),
        confirmation_repository=ConfirmationRepository(db),
        audit_repository=AuditRepository(db),
    )

    try:
        card = service.block_card(
            identity,
            card_reference=card_reference,
            confirmation_id=request.confirmation_id,
            correlation_id=correlation_id,
        )
        db.commit()

        return BlockCardResponse(
            card_reference=card.card_reference,
            status=card.status,
            correlation_id=correlation_id,
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
            detail="This card is not available to the authenticated customer.",
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
