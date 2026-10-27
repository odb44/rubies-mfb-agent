"""Create customer, account, and transaction tables.

Revision ID: 3dd831b584de
Revises:
Create Date: 2026-10-25 16:56:37.142928
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "3dd831b584de"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the customer, account, and transaction tables."""

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_reference", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=20), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("email", name=op.f("uq_customers_email")),
    )

    op.create_index(
        op.f("ix_customers_customer_reference"),
        "customers",
        ["customer_reference"],
        unique=True,
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("account_number", sa.String(length=10), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'NGN'"),
            nullable=False,
        ),
        sa.Column(
            "balance",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'BLOCKED', 'CLOSED')",
            name=op.f("ck_accounts_valid_account_status"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_accounts_customer_id_customers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint(
            "account_number",
            name=op.f("uq_accounts_account_number"),
        ),
    )

    op.create_index(
        op.f("ix_accounts_customer_id"),
        "accounts",
        ["customer_id"],
        unique=False,
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SUCCESSFUL', 'FAILED', 'REVERSED')",
            name=op.f("ck_transactions_valid_transaction_status"),
        ),
        sa.CheckConstraint(
            "transaction_type IN ('DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'PAYMENT')",
            name=op.f("ck_transactions_valid_transaction_type"),
        ),
        sa.CheckConstraint(
            "amount > 0",
            name=op.f("ck_transactions_amount_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_transactions_account_id_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint(
            "reference",
            name=op.f("uq_transactions_reference"),
        ),
    )

    op.create_index(
        op.f("ix_transactions_account_id"),
        "transactions",
        ["account_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the tables in dependency order."""

    op.drop_index(
        op.f("ix_transactions_account_id"),
        table_name="transactions",
    )
    op.drop_table("transactions")

    op.drop_index(
        op.f("ix_accounts_customer_id"),
        table_name="accounts",
    )
    op.drop_table("accounts")

    op.drop_index(
        op.f("ix_customers_customer_reference"),
        table_name="customers",
    )
    op.drop_table("customers")