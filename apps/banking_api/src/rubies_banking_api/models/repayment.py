from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.loan import Loan


class Repayment(Base):
    __tablename__ = "repayments"

    __table_args__ = (
        UniqueConstraint(
            "loan_id",
            "installment_number",
            name="uq_repayments_loan_installment",
        ),
        CheckConstraint(
            "installment_number > 0",
            name="installment_number_positive",
        ),
        CheckConstraint(
            "principal_due > 0",
            name="principal_due_positive",
        ),
        CheckConstraint(
            "status IN ('PAID', 'PENDING', 'OVERDUE')",
            name="valid_repayment_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    repayment_reference: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
        index=True,
    )

    loan_id: Mapped[int] = mapped_column(
        ForeignKey("loans.id"),
        nullable=False,
        index=True,
    )

    installment_number: Mapped[int] = mapped_column(
        nullable=False,
    )

    principal_due: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    loan: Mapped[Loan] = relationship(
        back_populates="repayments",
    )
