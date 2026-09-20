"""add tour program

Revision ID: c9b0f5a12d44
Revises: a72c4e19d530
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa


revision = "c9b0f5a12d44"
down_revision = "a72c4e19d530"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tour_types",
        sa.Column(
            "program",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "tour_types",
        "program",
    )
