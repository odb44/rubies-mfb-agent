
"""Read-only support desk endpoints for authenticated support staff."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from rubies_banking_api.api.support_staff_dependencies import (
    SupportStaffIdentity,
    get_support_staff_identity,
)
from rubies_banking_api.db.database import get_db
from rubies_banking_api.repositories.dispute_repository import DisputeRepository
from rubies_banking_api.repositories.support_handoff_repository import (
    SupportHandoffRepository,
)

router = APIRouter(
    prefix="/api/support-desk",
    tags=["Support Desk"],
)


class SupportDeskCustomer(BaseModel):
    """Customer identification displayed on the support desk."""

    customer_id: int
    customer_reference: str
    customer_name: str


class SupportDeskDisputeResponse(BaseModel):
    """Dispute record visible to authenticated support staff."""

    model_config = ConfigDict(from_attributes=True)

    case_reference: str
    customer_id: int
    customer_reference: str
    customer_name: str
    transaction_id: int | None
    category: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


class SupportDeskHandoffResponse(BaseModel):
    """Human support escalation visible to authenticated support staff."""

    model_config = ConfigDict(from_attributes=True)

    reference: str
    customer_id: int
    customer_reference: str
    customer_name: str
    status: str
    priority: str
    route: str
    reason: str
    summary: str
    actions_attempted: list[str]
    unresolved_questions: list[str]
    correlation_id: str | None
    failure_reason: str | None
    acknowledgement_reference: str | None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None


class SupportDeskDisputeListResponse(BaseModel):
    """Paginated dispute records."""

    items: list[SupportDeskDisputeResponse]
    limit: int
    offset: int


class SupportDeskHandoffListResponse(BaseModel):
    """Paginated human support escalation records."""

    items: list[SupportDeskHandoffResponse]
    limit: int
    offset: int


@router.get(
    "/disputes",
    response_model=SupportDeskDisputeListResponse,
)
def list_support_desk_disputes(
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        SupportStaffIdentity,
        Depends(get_support_staff_identity),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupportDeskDisputeListResponse:
    """List disputes across customers for authenticated support staff."""
    del identity

    repository = DisputeRepository(db)
    disputes = repository.list_all(limit=limit, offset=offset)

    items = [
        SupportDeskDisputeResponse(
            case_reference=dispute.case_reference,
            customer_id=dispute.customer_id,
            customer_reference=dispute.customer.customer_reference,
            customer_name=dispute.customer.full_name,
            transaction_id=dispute.transaction_id,
            category=dispute.category,
            description=dispute.description,
            status=dispute.status,
            created_at=dispute.created_at,
            updated_at=dispute.updated_at,
        )
        for dispute in disputes
    ]

    return SupportDeskDisputeListResponse(
        items=items,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/handoffs",
    response_model=SupportDeskHandoffListResponse,
)
def list_support_desk_handoffs(
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        SupportStaffIdentity,
        Depends(get_support_staff_identity),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupportDeskHandoffListResponse:
    """List human support escalations across customers."""
    del identity

    repository = SupportHandoffRepository(db)
    handoffs = repository.list_all(limit=limit, offset=offset)

    items = [
        SupportDeskHandoffResponse(
            reference=handoff.reference,
            customer_id=handoff.customer_id,
            customer_reference=handoff.customer.customer_reference,
            customer_name=handoff.customer.full_name,
            status=handoff.status,
            priority=handoff.priority,
            route=handoff.route,
            reason=handoff.reason,
            summary=handoff.summary,
            actions_attempted=handoff.actions_attempted,
            unresolved_questions=handoff.unresolved_questions,
            correlation_id=handoff.correlation_id,
            failure_reason=handoff.failure_reason,
            acknowledgement_reference=handoff.acknowledgement_reference,
            created_at=handoff.created_at,
            updated_at=handoff.updated_at,
            acknowledged_at=handoff.acknowledged_at,
        )
        for handoff in handoffs
    ]

    return SupportDeskHandoffListResponse(
        items=items,
        limit=limit,
        offset=offset,
    )
