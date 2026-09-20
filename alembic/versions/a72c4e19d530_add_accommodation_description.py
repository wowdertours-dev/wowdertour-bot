"""add accommodation description to tour types

Revision ID: a72c4e19d530
Revises: f41d9c6a2e10
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa


revision = "a72c4e19d530"
down_revision = "f41d9c6a2e10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tour_types",
        sa.Column(
            "accommodation_description",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "tour_types",
        "accommodation_description",
    )
