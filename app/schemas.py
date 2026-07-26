from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    unit_price: Decimal = Field(ge=0)
    quantity: int = Field(ge=0)
    reorder_level: int = Field(ge=0)


class ProductRead(ProductCreate):
    id: int
    active: bool
    is_low_stock: bool

    model_config = ConfigDict(from_attributes=True)


class InventoryAdjustment(BaseModel):
    quantity_delta: int
    movement_type: str = Field(default="adjustment", max_length=32)
    reference: str = Field(default="", max_length=120)
    note: str = ""


class OrderLineCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=160)
    customer_email: EmailStr
    items: list[OrderLineCreate] = Field(min_length=1)


class OrderItemRead(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderRead(BaseModel):
    id: int
    customer_name: str
    customer_email: str
    status: str
    total_amount: Decimal
    items: list[OrderItemRead]

    model_config = ConfigDict(from_attributes=True)
