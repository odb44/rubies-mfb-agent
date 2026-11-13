
"""add applicant profile provenance

Revision ID: 2fc7c2eaa44e
Revises: 129ed0ebef43
Create Date: 2026-11-01 12:55:48.107556

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2fc7c2eaa44e"
down_revision: str | Sequence[str] | None = "129ed0ebef43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # Do not invent provenance for existing applicant profiles.
    # If records already exist, stop and require explicit classification.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM loan_applicant_profiles
                ) THEN
                    RAISE EXCEPTION
                        'Cannot add mandatory profile_source: '
                        'loan_applicant_profiles contains existing records. '
                        'Classify their provenance before applying this migration.';
                END IF;
            END
            $$;
            """
        )
    )

    op.add_column(
        "loan_applicant_profiles",
        sa.Column(
            "profile_source",
            sa.String(length=30),
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "valid_applicant_profile_source",
        "loan_applicant_profiles",
        "profile_source IN ('SYNTHETIC_DEMO', 'CUSTOMER_PROVIDED')",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "valid_applicant_profile_source",
        "loan_applicant_profiles",
        type_="check",
    )

    op.drop_column(
        "loan_applicant_profiles",
        "profile_source",
    )
