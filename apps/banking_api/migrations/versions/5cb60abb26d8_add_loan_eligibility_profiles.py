
"""add loan eligibility profiles

Revision ID: 5cb60abb26d8
Revises: 2fc7c2eaa44e
Create Date: 2026-11-01 20:37:11.161795
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5cb60abb26d8"
down_revision: str | Sequence[str] | None = "2fc7c2eaa44e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the loan eligibility profile table."""

    op.create_table(
        "loan_eligibility_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("employment_type", sa.String(length=20), nullable=False),
        sa.Column(
            "monthly_income",
            sa.Numeric(precision=18, scale=2),
            nullable=True,
        ),
        sa.Column(
            "monthly_expenses",
            sa.Numeric(precision=18, scale=2),
            nullable=True,
        ),
        sa.Column(
            "existing_monthly_debt",
            sa.Numeric(precision=18, scale=2),
            nullable=True,
        ),
        sa.Column(
            "profile_source",
            sa.String(length=30),
            server_default="CUSTOMER_PROVIDED",
            nullable=False,
        ),
        sa.Column(
            "verification_status",
            sa.String(length=15),
            server_default="UNVERIFIED",
            nullable=False,
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "employment_type IN "
            "('SALARIED', 'SELF_EMPLOYED', 'BUSINESS_OWNER')",
            name=op.f(
                "ck_loan_eligibility_profiles_valid_eligibility_employment_type"
            ),
        ),
        sa.CheckConstraint(
            "profile_source = 'CUSTOMER_PROVIDED'",
            name=op.f(
                "ck_loan_eligibility_profiles_valid_eligibility_profile_source"
            ),
        ),
        sa.CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'VERIFIED')",
            name=op.f(
                "ck_loan_eligibility_profiles_valid_eligibility_verification_status"
            ),
        ),
        sa.CheckConstraint(
            "monthly_income IS NULL OR monthly_income >= 0",
            name=op.f(
                "ck_loan_eligibility_profiles_valid_eligibility_monthly_income"
            ),
        ),
        sa.CheckConstraint(
            "monthly_expenses IS NULL OR monthly_expenses >= 0",
            name=op.f(
                "ck_loan_eligibility_profiles_valid_eligibility_monthly_expenses"
            ),
        ),
        sa.CheckConstraint(
            "existing_monthly_debt IS NULL "
            "OR existing_monthly_debt >= 0",
            name=op.f(
                "ck_loan_eligibility_profiles_valid_eligibility_monthly_debt"
            ),
        ),
        sa.CheckConstraint(
            "(verification_status = 'UNVERIFIED' AND verified_at IS NULL) "
            "OR (verification_status = 'VERIFIED' AND verified_at IS NOT NULL)",
            name=op.f(
                "ck_loan_eligibility_profiles_valid_eligibility_verification_timestamp"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f(
                "fk_loan_eligibility_profiles_customer_id_customers"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_loan_eligibility_profiles"),
        ),
    )

    op.create_index(
        op.f("ix_loan_eligibility_profiles_customer_id"),
        "loan_eligibility_profiles",
        ["customer_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove the loan eligibility profile table."""

    op.drop_index(
        op.f("ix_loan_eligibility_profiles_customer_id"),
        table_name="loan_eligibility_profiles",
    )

    op.drop_table("loan_eligibility_profiles")
