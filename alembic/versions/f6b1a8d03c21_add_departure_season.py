"""add stored season to tour departures

Revision ID: f6b1a8d03c21
Revises: e5a9c7d42f10
"""

from alembic import op
import sqlalchemy as sa

revision = "f6b1a8d03c21"
down_revision = "e5a9c7d42f10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tour_departures",
        sa.Column("season", sa.String(length=20), nullable=True),
    )

    op.execute(
        """
        UPDATE tour_departures
        SET season =
            CASE
                WHEN EXTRACT(MONTH FROM start_date) >= 9
                THEN EXTRACT(YEAR FROM start_date)::int::text
                     || '/'
                     || RIGHT((EXTRACT(YEAR FROM start_date)::int + 1)::text, 2)
                ELSE (EXTRACT(YEAR FROM start_date)::int - 1)::text
                     || '/'
                     || RIGHT(EXTRACT(YEAR FROM start_date)::int::text, 2)
            END
        WHERE season IS NULL
        """
    )

    op.alter_column(
        "tour_departures",
        "season",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.create_index(
        "ix_tour_departures_season",
        "tour_departures",
        ["season"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tour_departures_season", table_name="tour_departures")
    op.drop_column("tour_departures", "season")
