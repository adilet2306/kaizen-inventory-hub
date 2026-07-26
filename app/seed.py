from decimal import Decimal

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import InventoryMovement, Product


def main() -> None:
    with SessionLocal() as db:
        count = db.scalar(select(func.count(Product.id))) or 0
        if count:
            print("Seed skipped: products already exist")
            return

        products = [
            Product(
                sku="LAPTOP-14",
                name="KaizenBook 14",
                description="14-inch training laptop",
                unit_price=Decimal("899.00"),
                quantity=12,
                reorder_level=4,
            ),
            Product(
                sku="DOCK-USBC",
                name="USB-C Dock",
                description="Dual-display USB-C docking station",
                unit_price=Decimal("149.00"),
                quantity=5,
                reorder_level=5,
            ),
            Product(
                sku="HEADSET-01",
                name="Training Headset",
                description="Noise-isolating USB headset",
                unit_price=Decimal("59.00"),
                quantity=2,
                reorder_level=6,
            ),
        ]
        db.add_all(products)
        db.flush()

        for product in products:
            db.add(
                InventoryMovement(
                    product_id=product.id,
                    movement_type="initial",
                    quantity_delta=product.quantity,
                    reference="seed",
                    note="Seed inventory",
                )
            )

        db.commit()
        print("Created three sample products")


if __name__ == "__main__":
    main()
