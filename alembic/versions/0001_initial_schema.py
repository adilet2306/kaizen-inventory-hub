"""initial inventory schema

Revision ID: 0001
Revises:
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_index("ix_products_name", "products", ["name"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_name", sa.String(length=160), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="placed"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_customer_email", "orders", ["customer_email"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_movements_product_id", "inventory_movements", ["product_id"])
    op.create_index("ix_inventory_movements_movement_type", "inventory_movements", ["movement_type"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    op.create_table(
        "low_stock_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity_snapshot", sa.Integer(), nullable=False),
        sa.Column("backend", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_low_stock_notifications_product_id", "low_stock_notifications", ["product_id"])


def downgrade() -> None:
    op.drop_table("low_stock_notifications")
    op.drop_table("order_items")
    op.drop_table("inventory_movements")
    op.drop_table("orders")
    op.drop_table("products")
