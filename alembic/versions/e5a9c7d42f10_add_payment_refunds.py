"""add payment refunds

Revision ID: e5a9c7d42f10
Revises: d4c8a2f71e90
"""

from alembic import op
import sqlalchemy as sa


revision = "e5a9c7d42f10"
down_revision = "d4c8a2f71e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="succeeded"),
        sa.Column("refund_method", sa.String(length=100), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_refunds_payment_id", "payment_refunds", ["payment_id"], unique=False)
    op.create_index("ix_payment_refunds_status", "payment_refunds", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_refunds_status", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_payment_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")
