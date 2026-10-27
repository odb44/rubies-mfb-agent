from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.account import Account


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="amount_positive",
        ),
        CheckConstraint(
            "transaction_type IN "
            "('DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'PAYMENT')",
            name="valid_transaction_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'SUCCESSFUL', 'FAILED', 'REVERSED')",
            name="valid_transaction_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    reference: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    account: Mapped[Account] = relationship(
        back_populates="transactions",
    )
