"""Request and response schemas for customer support handoffs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from rubies_banking_api.models.support_handoff import (
    HandoffPriority,
    HandoffRoute,
    HandoffStatus,
)


class SupportHandoffCreate(BaseModel):
    """Customer request for assistance from a human support team."""

    reason: str = Field(min_length=3, max_length=100)
    summary: str = Field(min_length=10, max_length=5000)
    route: HandoffRoute
    priority: HandoffPriority
    actions_attempted: list[str] = Field(default_factory=list, max_length=30)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=20)
    correlation_id: str | None = Field(default=None, max_length=100)


class SupportHandoffResponse(BaseModel):
    """Public representation of a support handoff."""

    model_config = ConfigDict(from_attributes=True)

    reference: str
    status: HandoffStatus
    priority: HandoffPriority
    route: HandoffRoute
    reason: str
    summary: str
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    acknowledgement_reference: str | None = None
    failure_reason: str | None = None
