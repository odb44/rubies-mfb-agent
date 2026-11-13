"""Database model for customer approval of sensitive banking actions."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from rubies_banking_api.db.base import Base


class Confirmation(Base):
    __tablename__ = "confirmations"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'CONSUMED')",
            name="valid_confirmation_status",
        ),
        Index("ix_confirmations_customer_status", "customer_id", "status"),
        Index("ix_confirmations_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    confirmation_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    customer_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Hash of the canonical action payload. Prevents approval from being
    # reused with different transaction details or other action parameters.
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
