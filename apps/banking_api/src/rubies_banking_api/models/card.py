from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.customer import Customer


class Card(Base):
    __tablename__ = "cards"

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'BLOCKED', 'EXPIRED')",
            name="valid_card_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    card_reference: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    masked_number: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
    )

    card_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DEBIT",
        server_default="DEBIT",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer: Mapped[Customer] = relationship()
