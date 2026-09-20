"""add category media

Revision ID: ec707fb6694f
Revises: b3dc59f0a740
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ec707fb6694f"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b3dc59f0a740"

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
    op.add_column(
        "tour_media",
        sa.Column(
            "category_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_tour_media_category_id",
        "tour_media",
        ["category_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_tour_media_category_id_tour_categories",
        "tour_media",
        "tour_categories",
        ["category_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tour_media_category_id_tour_categories",
        "tour_media",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_tour_media_category_id",
        table_name="tour_media",
    )

    op.drop_column(
        "tour_media",
        "category_id",
    )