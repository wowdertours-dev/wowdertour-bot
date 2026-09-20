"""add archived flag to tour departures

Revision ID: d4c8a2f71e90
Revises: c9b0f5a12d44
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa


revision = "d4c8a2f71e90"
down_revision = "c9b0f5a12d44"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tour_departures",
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_index(
        "ix_tour_departures_archived",
        "tour_departures",
        ["archived"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_tour_departures_archived",
        table_name="tour_departures",
    )

    op.drop_column(
        "tour_departures",
        "archived",
    )
