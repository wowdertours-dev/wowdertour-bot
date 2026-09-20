"""add tour media

Revision ID: b3dc59f0a740
Revises: 2c7a4f8d1b90
Create Date: 2026-09-03 12:46:44.718747
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3dc59f0a740"
down_revision: Union[str, Sequence[str], None] = (
    "2c7a4f8d1b90"
)
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "tour_media",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "tour_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "section",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "media_type",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "title",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "url",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "telegram_file_id",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["tour_id"],
            ["tour_types.id"],
        ),
    )

    op.create_index(
        "ix_tour_media_tour_id",
        "tour_media",
        ["tour_id"],
    )

    op.create_index(
        "ix_tour_media_section",
        "tour_media",
        ["section"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tour_media_section",
        table_name="tour_media",
    )

    op.drop_index(
        "ix_tour_media_tour_id",
        table_name="tour_media",
    )

    op.drop_table(
        "tour_media"
    )