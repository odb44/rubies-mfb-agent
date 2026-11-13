
"""add support staff

Revision ID: b7c21d8a4f60
Revises: a83482df6dc7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c21d8a4f60"
down_revision: str | Sequence[str] | None = "a83482df6dc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_staff",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_number", sa.String(30), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_staff")),
        sa.UniqueConstraint(
            "staff_number",
            name=op.f("uq_support_staff_staff_number"),
        ),
        sa.UniqueConstraint(
            "phone_number",
            name=op.f("uq_support_staff_phone_number"),
        ),
    )

    op.create_index(
        op.f("ix_support_staff_staff_number"),
        "support_staff",
        ["staff_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_support_staff_staff_number"),
        table_name="support_staff",
    )
    op.drop_table("support_staff")

