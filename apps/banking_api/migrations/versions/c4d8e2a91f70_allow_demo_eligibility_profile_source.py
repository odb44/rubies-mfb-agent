"""allow demo eligibility profile source

Revision ID: c4d8e2a91f70
Revises: 5cb60abb26d8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c4d8e2a91f70"
down_revision: str | Sequence[str] | None = "5cb60abb26d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "valid_eligibility_profile_source",
        "loan_eligibility_profiles",
        type_="check",
    )

    op.create_check_constraint(
        "valid_eligibility_profile_source",
        "loan_eligibility_profiles",
        "profile_source IN ('CUSTOMER_PROVIDED', 'DEMO_FIXTURE')",
    )


def downgrade() -> None:
    demo_profiles_exist = op.get_bind().execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM loan_eligibility_profiles
                WHERE profile_source = 'DEMO_FIXTURE'
            )
            """
        )
    ).scalar_one()

    if demo_profiles_exist:
        raise RuntimeError(
            "Cannot downgrade while DEMO_FIXTURE profiles exist. "
            "Remove those fixtures explicitly before downgrading."
        )

    op.drop_constraint(
        "valid_eligibility_profile_source",
        "loan_eligibility_profiles",
        type_="check",
    )

    op.create_check_constraint(
        "valid_eligibility_profile_source",
        "loan_eligibility_profiles",
        "profile_source = 'CUSTOMER_PROVIDED'",
    )