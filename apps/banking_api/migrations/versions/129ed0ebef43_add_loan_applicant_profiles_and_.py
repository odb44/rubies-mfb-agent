
"""add loan applicant profiles and application terms

Revision ID: 129ed0ebef43
Revises: b7c21d8a4f60
Create Date: 2026-11-01 12:50:21.005702

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "129ed0ebef43"
down_revision: str | Sequence[str] | None = "b7c21d8a4f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add loan term to existing applications.
    # Nullable because existing applications have no verified term.
    op.add_column(
        "loan_applications",
        sa.Column(
            "term_months",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "valid_loan_application_term",
        "loan_applications",
        "term_months IS NULL OR term_months > 0",
    )

    # Create applicant profiles.
    op.create_table(
        "loan_applicant_profiles",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "gender",
            sa.String(length=10),
            nullable=True,
        ),
        sa.Column(
            "married",
            sa.String(length=5),
            nullable=True,
        ),
        sa.Column(
            "dependents",
            sa.String(length=2),
            nullable=True,
        ),
        sa.Column(
            "education",
            sa.String(length=20),
            nullable=True,
        ),
        sa.Column(
            "self_employed",
            sa.String(length=5),
            nullable=True,
        ),
        sa.Column(
            "applicant_income",
            sa.Numeric(18, 2),
            nullable=True,
        ),
        sa.Column(
            "coapplicant_income",
            sa.Numeric(18, 2),
            nullable=True,
        ),
        sa.Column(
            "credit_history",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "property_area",
            sa.String(length=10),
            nullable=True,
        ),
        sa.CheckConstraint(
            "gender IS NULL OR gender IN ('Male', 'Female')",
            name="valid_applicant_gender",
        ),
        sa.CheckConstraint(
            "married IS NULL OR married IN ('Yes', 'No')",
            name="valid_applicant_marital_status",
        ),
        sa.CheckConstraint(
            "dependents IS NULL OR dependents IN ('0', '1', '2', '3+')",
            name="valid_applicant_dependents",
        ),
        sa.CheckConstraint(
            "education IS NULL OR education IN ('Graduate', 'Not Graduate')",
            name="valid_applicant_education",
        ),
        sa.CheckConstraint(
            "self_employed IS NULL OR self_employed IN ('Yes', 'No')",
            name="valid_applicant_employment_status",
        ),
        sa.CheckConstraint(
            "applicant_income IS NULL OR applicant_income >= 0",
            name="valid_applicant_income",
        ),
        sa.CheckConstraint(
            "coapplicant_income IS NULL OR coapplicant_income >= 0",
            name="valid_coapplicant_income",
        ),
        sa.CheckConstraint(
            "credit_history IS NULL OR credit_history IN (0, 1)",
            name="valid_applicant_credit_history",
        ),
        sa.CheckConstraint(
            "property_area IS NULL OR property_area IN "
            "('Urban', 'Semiurban', 'Rural')",
            name="valid_applicant_property_area",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_loan_applicant_profiles_customer_id_customers",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "customer_id",
            name="uq_loan_applicant_profiles_customer_id",
        ),
    )

    op.create_index(
        "ix_loan_applicant_profiles_customer_id",
        "loan_applicant_profiles",
        ["customer_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_loan_applicant_profiles_customer_id",
        table_name="loan_applicant_profiles",
    )

    op.drop_table("loan_applicant_profiles")

    op.drop_constraint(
        "valid_loan_application_term",
        "loan_applications",
        type_="check",
    )

    op.drop_column(
        "loan_applications",
        "term_months",
    )
