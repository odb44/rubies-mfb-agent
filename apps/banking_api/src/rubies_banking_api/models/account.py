from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rubies_banking_api.db.base import Base

if TYPE_CHECKING:
    from rubies_banking_api.models.customer import Customer

if TYPE_CHECKING:
    from rubies_banking_api.models.transaction import Transaction


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    account_number: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default=text("'ACTIVE'"),
    )

    customer: Mapped[Customer] = relationship(
        back_populates="accounts",
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="account",
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'BLOCKED', 'CLOSED')",
            name="valid_account_status",
        ),
    )
