from decimal import Decimal

from sqlalchemy import select

from app.alerts import send_low_stock_alerts
from app.database import SessionLocal
from app.models import LowStockNotification, Product
from app.schemas import ProductCreate
from app.services import create_product


def create_sample_product(client, *, sku="KB-100", quantity=10, reorder_level=3, price="25.00"):
    response = client.post(
        "/api/products",
        json={
            "sku": sku,
            "name": f"Product {sku}",
            "description": "Test product",
            "unit_price": price,
            "quantity": quantity,
            "reorder_level": reorder_level,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_ready_version_and_instance(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {
        "status": "ready",
        "database": "connected",
    }
    version = client.get("/version").json()
    assert version["name"] == "Kaizen Inventory Hub"
    assert version["environment"] == "test"
    assert "hostname" in client.get("/instance").json()


def test_create_and_list_product(client):
    product = create_sample_product(client)
    products = client.get("/api/products").json()
    assert len(products) == 1
    assert products[0]["id"] == product["id"]
    assert products[0]["sku"] == "KB-100"
    assert products[0]["quantity"] == 10
    assert products[0]["is_low_stock"] is False


def test_duplicate_sku_is_rejected(client):
    create_sample_product(client)
    response = client.post(
        "/api/products",
        json={
            "sku": "kb-100",
            "name": "Duplicate",
            "description": "",
            "unit_price": "10.00",
            "quantity": 1,
            "reorder_level": 1,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "SKU already exists"


def test_inventory_adjustment_and_negative_protection(client):
    product = create_sample_product(client, quantity=5)
    response = client.post(
        f"/api/products/{product['id']}/adjust",
        json={
            "quantity_delta": 4,
            "movement_type": "restock",
            "reference": "PO-10",
            "note": "Restocked",
        },
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 9

    response = client.post(
        f"/api/products/{product['id']}/adjust",
        json={"quantity_delta": -10, "movement_type": "adjustment"},
    )
    assert response.status_code == 400


def test_order_reduces_stock_and_calculates_total(client):
    product = create_sample_product(client, quantity=8, price="12.50")
    response = client.post(
        "/api/orders",
        json={
            "customer_name": "Ada Lovelace",
            "customer_email": "ada@example.com",
            "items": [{"product_id": product["id"], "quantity": 3}],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["total_amount"] == "37.50"

    products = client.get("/api/products").json()
    assert products[0]["quantity"] == 5

    orders = client.get("/api/orders").json()
    assert orders[0]["items"][0]["quantity"] == 3
    assert orders[0]["items"][0]["line_total"] == "37.50"


def test_order_rejects_insufficient_stock(client):
    product = create_sample_product(client, quantity=2)
    response = client.post(
        "/api/orders",
        json={
            "customer_name": "Grace Hopper",
            "customer_email": "grace@example.com",
            "items": [{"product_id": product["id"], "quantity": 3}],
        },
    )
    assert response.status_code == 409
    assert "Insufficient stock" in response.json()["detail"]


def test_low_stock_alert_is_recorded_and_deduplicated(client, capsys):
    create_sample_product(client, quantity=2, reorder_level=3)

    with SessionLocal() as db:
        sent, skipped = send_low_stock_alerts(db)
        assert (sent, skipped) == (1, 0)
        notification_count = len(list(db.scalars(select(LowStockNotification))))
        assert notification_count == 1

    output = capsys.readouterr().out
    assert "Low stock: KB-100" in output

    with SessionLocal() as db:
        sent, skipped = send_low_stock_alerts(db)
        assert (sent, skipped) == (0, 1)


def test_dashboard_and_low_stock_csv(client):
    create_sample_product(client, quantity=1, reorder_level=2)
    assert client.get("/").status_code == 200
    assert client.get("/products").status_code == 200
    response = client.get("/reports/low-stock.csv")
    assert response.status_code == 200
    assert "KB-100" in response.text


def test_service_layer_accepts_decimal_values():
    with SessionLocal() as db:
        product = create_product(
            db,
            ProductCreate(
                sku="DEC-1",
                name="Decimal Product",
                unit_price=Decimal("19.99"),
                quantity=1,
                reorder_level=1,
            ),
        )
        assert product.unit_price == Decimal("19.99")
        assert db.scalar(select(Product).where(Product.sku == "DEC-1")) is not None
