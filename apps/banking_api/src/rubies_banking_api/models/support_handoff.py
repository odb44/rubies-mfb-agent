
"""Persistent records for customer support handoffs."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.customer import Customer


class HandoffStatus(StrEnum):
    """Lifecycle states for a support handoff."""

    PENDING_ACKNOWLEDGEMENT = "PENDING_ACKNOWLEDGEMENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"


class HandoffPriority(StrEnum):
    """Support routing priorities."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class HandoffRoute(StrEnum):
    """Supported synthetic support destinations."""

    PAYMENTS_OPERATIONS = "PAYMENTS_OPERATIONS"
    CARD_SUPPORT = "CARD_SUPPORT"
    FRAUD_AND_SECURITY = "FRAUD_AND_SECURITY"
    CUSTOMER_EXPERIENCE = "CUSTOMER_EXPERIENCE"
    ACCOUNT_SERVICES = "ACCOUNT_SERVICES"
    LENDING_OPERATIONS = "LENDING_OPERATIONS"
    GENERAL_HUMAN_SUPPORT = "GENERAL_HUMAN_SUPPORT"


class SupportHandoff(Base):
    """A durable record of a request for human assistance."""

    __tablename__ = "support_handoffs"

    __table_args__ = (
        CheckConstraint(
            "priority IN ('P1', 'P2', 'P3', 'P4')",
            name="valid_priority",
        ),
        Index(
            "ix_support_handoffs_customer_created",
            "customer_id",
            "created_at",
        ),
        Index(
            "ix_support_handoffs_status_created",
            "status",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    reference: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
        default=lambda: f"HND-{uuid4().hex.upper()}",
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer: Mapped["Customer"] = relationship()

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=HandoffStatus.PENDING_ACKNOWLEDGEMENT.value,
    )

    priority: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    route: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    actions_attempted: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    unresolved_questions: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    correlation_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
    )

    acknowledgement_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
