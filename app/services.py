from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import InventoryMovement, Order, OrderItem, Product
from app.schemas import InventoryAdjustment, OrderCreate, ProductCreate


def create_product(db: Session, payload: ProductCreate) -> Product:
    sku = payload.sku.strip().upper()
    existing = db.scalar(select(Product).where(Product.sku == sku))
    if existing:
        raise HTTPException(status_code=409, detail="SKU already exists")

    product = Product(
        sku=sku,
        name=payload.name.strip(),
        description=payload.description.strip(),
        unit_price=payload.unit_price,
        quantity=payload.quantity,
        reorder_level=payload.reorder_level,
    )
    db.add(product)
    db.flush()

    if payload.quantity:
        db.add(
            InventoryMovement(
                product_id=product.id,
                movement_type="initial",
                quantity_delta=payload.quantity,
                reference="product-create",
                note="Initial inventory",
            )
        )

    db.commit()
    db.refresh(product)
    return product


def adjust_inventory(
    db: Session, product: Product, payload: InventoryAdjustment
) -> Product:
    new_quantity = product.quantity + payload.quantity_delta
    if new_quantity < 0:
        raise HTTPException(status_code=400, detail="Adjustment would make stock negative")

    product.quantity = new_quantity
    db.add(
        InventoryMovement(
            product_id=product.id,
            movement_type=payload.movement_type.strip() or "adjustment",
            quantity_delta=payload.quantity_delta,
            reference=payload.reference.strip(),
            note=payload.note.strip(),
        )
    )
    db.commit()
    db.refresh(product)
    return product


def create_order(db: Session, payload: OrderCreate) -> Order:
    requested: dict[int, int] = {}
    for line in payload.items:
        requested[line.product_id] = requested.get(line.product_id, 0) + line.quantity

    product_ids = list(requested)
    products = list(
        db.scalars(
            select(Product)
            .where(Product.id.in_(product_ids), Product.active.is_(True))
            .with_for_update()
        )
    )
    products_by_id = {product.id: product for product in products}

    missing = [product_id for product_id in product_ids if product_id not in products_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Products not found: {missing}")

    for product_id, quantity in requested.items():
        product = products_by_id[product_id]
        if product.quantity < quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for {product.sku}: available={product.quantity}",
            )

    order = Order(
        customer_name=payload.customer_name.strip(),
        customer_email=str(payload.customer_email).strip().lower(),
        status="placed",
        total_amount=Decimal("0.00"),
    )
    db.add(order)
    db.flush()

    total = Decimal("0.00")
    for product_id, quantity in requested.items():
        product = products_by_id[product_id]
        line_total = product.unit_price * quantity
        product.quantity -= quantity
        total += line_total

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.unit_price,
                line_total=line_total,
            )
        )
        db.add(
            InventoryMovement(
                product_id=product.id,
                movement_type="sale",
                quantity_delta=-quantity,
                reference=f"order-{order.id}",
                note=f"Order for {payload.customer_email}",
            )
        )

    order.total_amount = total
    db.commit()

    return db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )
