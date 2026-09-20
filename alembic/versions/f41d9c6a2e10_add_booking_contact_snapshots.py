"""add booking contact snapshots

Revision ID: f41d9c6a2e10
Revises: ec707fb6694f
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "f41d9c6a2e10"
down_revision = "ec707fb6694f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bookings",
        sa.Column(
            "applicant_full_name",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "bookings",
        sa.Column(
            "applicant_phone",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "bookings",
        sa.Column(
            "applicant_telegram_username",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "bookings",
        sa.Column(
            "applicant_telegram_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_bookings_applicant_telegram_id",
        "bookings",
        ["applicant_telegram_id"],
        unique=False,
    )

    # Существующие заявки получают снимок из текущего Customer.
    op.execute(
        """
        UPDATE bookings AS b
        SET
            applicant_full_name = c.full_name,
            applicant_phone = c.phone,
            applicant_telegram_username = c.telegram_username,
            applicant_telegram_id = c.telegram_id
        FROM customers AS c
        WHERE c.id = b.customer_id
        """
    )


def downgrade():
    op.drop_index(
        "ix_bookings_applicant_telegram_id",
        table_name="bookings",
    )

    op.drop_column(
        "bookings",
        "applicant_telegram_id",
    )
    op.drop_column(
        "bookings",
        "applicant_telegram_username",
    )
    op.drop_column(
        "bookings",
        "applicant_phone",
    )
    op.drop_column(
        "bookings",
        "applicant_full_name",
    )
