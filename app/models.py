from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=5)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")
    notifications: Mapped[list["LowStockNotification"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    @property
    def is_low_stock(self) -> bool:
        return self.active and self.quantity <= self.reorder_level


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(32), index=True)
    quantity_delta: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="movements")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    customer_email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="placed", index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")


class LowStockNotification(Base):
    __tablename__ = "low_stock_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity_snapshot: Mapped[int] = mapped_column(Integer)
    backend: Mapped[str] = mapped_column(String(32))
    message_id: Mapped[str] = mapped_column(String(255), default="")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="notifications")
