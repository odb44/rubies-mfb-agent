from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.customer import Customer
    from rubies_banking_api.models.transaction import Transaction


class Dispute(Base):
    __tablename__ = "disputes"

    __table_args__ = (
        CheckConstraint(
            "category IN ("
            "'TRANSFER_FAILED_DEBITED', "
            "'TRANSFER_DELAYED_OR_UNKNOWN', "
            "'DUPLICATE_DEBIT', "
            "'BENEFICIARY_NOT_CREDITED', "
            "'CARD_LOST_OR_STOLEN', "
            "'UNRECOGNIZED_TRANSACTION', "
            "'FEE_OR_CHARGE_QUERY', "
            "'ACCOUNT_ACCESS_OR_KYC', "
            "'LOAN_QUERY_OR_COMPLAINT', "
            "'SERVICE_OR_STAFF_COMPLAINT', "
            "'OTHER_OR_UNCLEAR'"
            ")",
            name="valid_dispute_category",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'IN_REVIEW', 'AWAITING_CUSTOMER', "
            "'RESOLVED', 'CLOSED')",
            name="valid_dispute_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    case_reference: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"),
        nullable=True,
        index=True,
    )

    category: Mapped[str] = mapped_column(String(40), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="OPEN",
        server_default="OPEN",
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

    transaction: Mapped[Transaction | None] = relationship()