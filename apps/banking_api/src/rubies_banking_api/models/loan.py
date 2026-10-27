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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.loan_application import LoanApplication
    from rubies_banking_api.models.repayment import Repayment


class Loan(Base):
    __tablename__ = "loans"

    __table_args__ = (
        CheckConstraint(
            "principal > 0",
            name="principal_positive",
        ),
        CheckConstraint(
            "outstanding_balance >= 0 "
            "AND outstanding_balance <= principal",
            name="valid_outstanding_balance",
        ),
        CheckConstraint(
            "term_months > 0",
            name="term_months_positive",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'OVERDUE', 'REPAID')",
            name="valid_loan_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    loan_reference: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
        index=True,
    )

    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"),
        unique=True,
        nullable=False,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    principal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default="NGN",
    )

    term_months: Mapped[int] = mapped_column(
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    disbursed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    application: Mapped[LoanApplication] = relationship(
        back_populates="loan",
    )

    repayments: Mapped[list[Repayment]] = relationship(
        back_populates="loan",
        cascade="all, delete-orphan",
    )