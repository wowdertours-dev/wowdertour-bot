"""add tour categories

Revision ID: 2c7a4f8d1b90
Revises: 11d1d6bf2700
Create Date: 2026-09-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2c7a4f8d1b90"
down_revision: Union[str, None] = "11d1d6bf2700"
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
        "tour_categories",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "slug",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "emoji",
            sa.String(length=20),
            nullable=True,
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_index(
        op.f(
            "ix_tour_categories_slug"
        ),
        "tour_categories",
        ["slug"],
        unique=True,
    )

    op.add_column(
        "tour_types",
        sa.Column(
            "category_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        op.f(
            "ix_tour_types_category_id"
        ),
        "tour_types",
        ["category_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_tour_types_category_id",
        "tour_types",
        "tour_categories",
        ["category_id"],
        ["id"],
    )

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            INSERT INTO tour_categories
                (
                    slug,
                    title,
                    emoji,
                    sort_order,
                    active
                )
            VALUES
                (
                    'snowboard',
                    'Сноуборд-туры',
                    '🏂',
                    10,
                    TRUE
                ),
                (
                    'wake',
                    'Вейк-туры',
                    '🏄',
                    20,
                    TRUE
                ),
                (
                    'skate',
                    'Скейт-интенсивы',
                    '🛹',
                    30,
                    TRUE
                )
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE tour_types
            SET category_id = (
                SELECT id
                FROM tour_categories
                WHERE slug = 'snowboard'
            )
            WHERE slug IN (
                'kirovsk',
                'sheregesh'
            )
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE tour_types
            SET category_id = (
                SELECT id
                FROM tour_categories
                WHERE slug = 'wake'
            )
            WHERE
                LOWER(slug) LIKE '%wake%'
                OR LOWER(title)
                    LIKE '%вейк%'
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE tour_types
            SET category_id = (
                SELECT id
                FROM tour_categories
                WHERE slug = 'skate'
            )
            WHERE
                LOWER(slug) LIKE '%skate%'
                OR LOWER(title)
                    LIKE '%скейт%'
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE tour_types
            SET category_id = (
                SELECT id
                FROM tour_categories
                WHERE slug = 'snowboard'
            )
            WHERE category_id IS NULL
            """
        )
    )

    op.alter_column(
        "tour_types",
        "category_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tour_types_category_id",
        "tour_types",
        type_="foreignkey",
    )

    op.drop_index(
        op.f(
            "ix_tour_types_category_id"
        ),
        table_name="tour_types",
    )

    op.drop_column(
        "tour_types",
        "category_id",
    )

    op.drop_index(
        op.f(
            "ix_tour_categories_slug"
        ),
        table_name="tour_categories",
    )

    op.drop_table(
        "tour_categories"
    )