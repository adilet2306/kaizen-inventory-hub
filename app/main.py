import csv
import io
import os
import socket
from decimal import Decimal, InvalidOperation

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.alerts import low_stock_products
from app.config import PROJECT_ROOT, get_settings
from app.database import get_db
from app.models import InventoryMovement, Order, OrderItem, Product
from app.schemas import InventoryAdjustment, OrderCreate, OrderLineCreate, ProductCreate
from app.services import adjust_inventory, create_order, create_product

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")
templates = Jinja2Templates(directory=PROJECT_ROOT / "app" / "templates")


def money(value: Decimal | float | int) -> str:
    return f"${Decimal(value):,.2f}"


templates.env.filters["money"] = money


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    products = list(db.scalars(select(Product).order_by(Product.name)))
    low_stock = [product for product in products if product.is_low_stock]
    total_units = sum(product.quantity for product in products)
    inventory_value = sum(product.unit_price * product.quantity for product in products)
    order_count = db.scalar(select(func.count(Order.id))) or 0
    recent_orders = list(
        db.scalars(select(Order).order_by(Order.created_at.desc()).limit(5))
    )
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "products": products,
            "low_stock": low_stock,
            "total_units": total_units,
            "inventory_value": inventory_value,
            "order_count": order_count,
            "recent_orders": recent_orders,
        },
    )


@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request, db: Session = Depends(get_db)):
    products = list(db.scalars(select(Product).order_by(Product.name)))
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={"products": products},
    )


@app.get("/products/new", response_class=HTMLResponse)
def new_product_page(request: Request):
    return templates.TemplateResponse(request=request, name="product_new.html", context={})


@app.post("/products")
def create_product_form(
    sku: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    unit_price: str = Form(...),
    quantity: int = Form(...),
    reorder_level: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        payload = ProductCreate(
            sku=sku,
            name=name,
            description=description,
            unit_price=Decimal(unit_price),
            quantity=quantity,
            reorder_level=reorder_level,
        )
    except (ValidationError, InvalidOperation) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    product = create_product(db, payload)
    return RedirectResponse(url=f"/products/{product.id}", status_code=303)


@app.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    movements = list(
        db.scalars(
            select(InventoryMovement)
            .where(InventoryMovement.product_id == product_id)
            .order_by(InventoryMovement.created_at.desc())
        )
    )
    return templates.TemplateResponse(
        request=request,
        name="product_detail.html",
        context={"product": product, "movements": movements},
    )


@app.post("/products/{product_id}/adjust")
def adjust_product_form(
    product_id: int,
    quantity_delta: int = Form(...),
    movement_type: str = Form("adjustment"),
    reference: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    product = db.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    adjust_inventory(
        db,
        product,
        InventoryAdjustment(
            quantity_delta=quantity_delta,
            movement_type=movement_type,
            reference=reference,
            note=note,
        ),
    )
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)


@app.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request, db: Session = Depends(get_db)):
    orders = list(db.scalars(select(Order).order_by(Order.created_at.desc())))
    return templates.TemplateResponse(
        request=request,
        name="orders.html",
        context={"orders": orders},
    )


@app.get("/orders/new", response_class=HTMLResponse)
def new_order_page(request: Request, db: Session = Depends(get_db)):
    products = list(
        db.scalars(
            select(Product)
            .where(Product.active.is_(True), Product.quantity > 0)
            .order_by(Product.name)
        )
    )
    return templates.TemplateResponse(
        request=request,
        name="order_new.html",
        context={"products": products},
    )


@app.post("/orders")
def create_order_form(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        payload = OrderCreate(
            customer_name=customer_name,
            customer_email=customer_email,
            items=[OrderLineCreate(product_id=product_id, quantity=quantity)],
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    order = create_order(db, payload)
    return RedirectResponse(url=f"/orders/{order.id}", status_code=303)


@app.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse(
        request=request,
        name="order_detail.html",
        context={"order": order},
    )


@app.get("/reports/low-stock.csv")
def low_stock_csv(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sku", "name", "quantity", "reorder_level", "unit_price"])
    for product in low_stock_products(db):
        writer.writerow(
            [product.sku, product.name, product.quantity, product.reorder_level, product.unit_price]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=low-stock.csv"},
    )


@app.get("/api/products")
def api_products(db: Session = Depends(get_db)):
    products = list(db.scalars(select(Product).order_by(Product.id)))
    return [
        {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "unit_price": str(product.unit_price),
            "quantity": product.quantity,
            "reorder_level": product.reorder_level,
            "active": product.active,
            "is_low_stock": product.is_low_stock,
        }
        for product in products
    ]


@app.post("/api/products", status_code=201)
def api_create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = create_product(db, payload)
    return {"id": product.id, "sku": product.sku, "quantity": product.quantity}


@app.post("/api/products/{product_id}/adjust")
def api_adjust_product(
    product_id: int,
    payload: InventoryAdjustment,
    db: Session = Depends(get_db),
):
    product = db.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    product = adjust_inventory(db, product, payload)
    return {"id": product.id, "sku": product.sku, "quantity": product.quantity}


@app.get("/api/orders")
def api_orders(db: Session = Depends(get_db)):
    orders = list(
        db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .order_by(Order.id)
        )
    )
    return [
        {
            "id": order.id,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "status": order.status,
            "total_amount": str(order.total_amount),
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "line_total": str(item.line_total),
                }
                for item in order.items
            ],
        }
        for order in orders
    ]


@app.post("/api/orders", status_code=201)
def api_create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    order = create_order(db, payload)
    return {
        "id": order.id,
        "status": order.status,
        "total_amount": str(order.total_amount),
    }


@app.get("/api/low-stock")
def api_low_stock(db: Session = Depends(get_db)):
    return [
        {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "quantity": product.quantity,
            "reorder_level": product.reorder_level,
        }
        for product in low_stock_products(db)
    ]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready", "database": "connected"}


@app.get("/version")
def version():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@app.get("/instance")
def instance():
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
    }


@app.get("/metrics", response_class=Response)
def metrics(db: Session = Depends(get_db)):
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="metrics disabled")

    product_count = db.scalar(select(func.count(Product.id))) or 0
    low_stock_count = db.scalar(
        select(func.count(Product.id)).where(
            Product.active.is_(True), Product.quantity <= Product.reorder_level
        )
    ) or 0
    order_count = db.scalar(select(func.count(Order.id))) or 0
    inventory_units = db.scalar(select(func.coalesce(func.sum(Product.quantity), 0))) or 0

    body = "\n".join(
        [
            "# HELP inventory_products_total Total number of products.",
            "# TYPE inventory_products_total gauge",
            f"inventory_products_total {product_count}",
            "# HELP inventory_low_stock_products Number of low-stock products.",
            "# TYPE inventory_low_stock_products gauge",
            f"inventory_low_stock_products {low_stock_count}",
            "# HELP inventory_orders_total Total number of orders.",
            "# TYPE inventory_orders_total gauge",
            f"inventory_orders_total {order_count}",
            "# HELP inventory_units_total Total units currently in stock.",
            "# TYPE inventory_units_total gauge",
            f"inventory_units_total {inventory_units}",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")
