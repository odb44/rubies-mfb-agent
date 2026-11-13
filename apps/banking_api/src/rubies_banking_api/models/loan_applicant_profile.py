
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.customer import Customer


class LoanApplicantProfile(Base):
    __tablename__ = "loan_applicant_profiles"

    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            name="uq_loan_applicant_profiles_customer_id",
        ),
        CheckConstraint(
            "profile_source IN ('SYNTHETIC_DEMO', 'CUSTOMER_PROVIDED')",
            name="valid_applicant_profile_source",
        ),
        CheckConstraint(
            "gender IS NULL OR gender IN ('Male', 'Female')",
            name="valid_applicant_gender",
        ),
        CheckConstraint(
            "married IS NULL OR married IN ('Yes', 'No')",
            name="valid_applicant_marital_status",
        ),
        CheckConstraint(
            "dependents IS NULL OR dependents IN ('0', '1', '2', '3+')",
            name="valid_applicant_dependents",
        ),
        CheckConstraint(
            "education IS NULL OR education IN ('Graduate', 'Not Graduate')",
            name="valid_applicant_education",
        ),
        CheckConstraint(
            "self_employed IS NULL OR self_employed IN ('Yes', 'No')",
            name="valid_applicant_employment_status",
        ),
        CheckConstraint(
            "applicant_income IS NULL OR applicant_income >= 0",
            name="valid_applicant_income",
        ),
        CheckConstraint(
            "coapplicant_income IS NULL OR coapplicant_income >= 0",
            name="valid_coapplicant_income",
        ),
        CheckConstraint(
            "credit_history IS NULL OR credit_history IN (0, 1)",
            name="valid_applicant_credit_history",
        ),
        CheckConstraint(
            "property_area IS NULL OR property_area IN "
            "('Urban', 'Semiurban', 'Rural')",
            name="valid_applicant_property_area",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    profile_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    gender: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    married: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
    )

    dependents: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
    )

    education: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    self_employed: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
    )

    applicant_income: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )

    coapplicant_income: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )

    credit_history: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    property_area: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    customer: Mapped[Customer] = relationship(
        back_populates="loan_applicant_profile",
    )
