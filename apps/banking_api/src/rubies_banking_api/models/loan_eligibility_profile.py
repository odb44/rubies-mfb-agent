
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
    from rubies_banking_api.models.customer import Customer


class LoanEligibilityProfile(Base):
    __tablename__ = "loan_eligibility_profiles"

    __table_args__ = (
        CheckConstraint(
            "employment_type IN "
            "('SALARIED', 'SELF_EMPLOYED', 'BUSINESS_OWNER')",
            name="valid_eligibility_employment_type",
        ),
        CheckConstraint(
            "profile_source IN ('CUSTOMER_PROVIDED', 'DEMO_FIXTURE')",
            name="valid_eligibility_profile_source",
        ),
        CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'VERIFIED')",
            name="valid_eligibility_verification_status",
        ),
        CheckConstraint(
            "monthly_income IS NULL OR monthly_income >= 0",
            name="valid_eligibility_monthly_income",
        ),
        CheckConstraint(
            "monthly_expenses IS NULL OR monthly_expenses >= 0",
            name="valid_eligibility_monthly_expenses",
        ),
        CheckConstraint(
            "existing_monthly_debt IS NULL OR existing_monthly_debt >= 0",
            name="valid_eligibility_monthly_debt",
        ),
        CheckConstraint(
            "(verification_status = 'UNVERIFIED' AND verified_at IS NULL) "
            "OR (verification_status = 'VERIFIED' AND verified_at IS NOT NULL)",
            name="valid_eligibility_verification_timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    employment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    monthly_income: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )

    monthly_expenses: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )

    existing_monthly_debt: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )

    profile_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="CUSTOMER_PROVIDED",
        server_default="CUSTOMER_PROVIDED",
    )

    verification_status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        default="UNVERIFIED",
        server_default="UNVERIFIED",
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer: Mapped[Customer] = relationship(
        back_populates="loan_eligibility_profile",
    )
