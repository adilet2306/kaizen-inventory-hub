from datetime import datetime, timedelta, timezone

import boto3
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LowStockNotification, Product


def low_stock_products(db: Session) -> list[Product]:
    return list(
        db.scalars(
            select(Product)
            .where(Product.active.is_(True), Product.quantity <= Product.reorder_level)
            .order_by(Product.quantity.asc(), Product.name.asc())
        )
    )


def _recent_duplicate(db: Session, product: Product, cooldown_minutes: int) -> bool:
    latest = db.scalar(
        select(LowStockNotification)
        .where(LowStockNotification.product_id == product.id)
        .order_by(desc(LowStockNotification.sent_at))
        .limit(1)
    )
    if latest is None:
        return False

    sent_at = latest.sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    return latest.quantity_snapshot == product.quantity and sent_at >= cutoff


def send_low_stock_alerts(db: Session) -> tuple[int, int]:
    settings = get_settings()
    products = low_stock_products(db)
    sent = 0
    skipped = 0

    sns = None
    if settings.alert_backend.lower() == "sns":
        if not settings.sns_topic_arn:
            raise RuntimeError("SNS_TOPIC_ARN is required when ALERT_BACKEND=sns")
        sns = boto3.client("sns", region_name=settings.aws_region)

    for product in products:
        if _recent_duplicate(db, product, settings.low_stock_cooldown_minutes):
            skipped += 1
            continue

        message = (
            f"Low stock: {product.sku} - {product.name}\n"
            f"Current quantity: {product.quantity}\n"
            f"Reorder level: {product.reorder_level}"
        )
        message_id = ""

        if settings.alert_backend.lower() == "console":
            print(message)
        elif settings.alert_backend.lower() == "sns":
            assert sns is not None
            response = sns.publish(
                TopicArn=settings.sns_topic_arn,
                Subject=f"Low stock: {product.sku}",
                Message=message,
            )
            message_id = response.get("MessageId", "")
        else:
            raise RuntimeError(f"Unsupported ALERT_BACKEND={settings.alert_backend}")

        db.add(
            LowStockNotification(
                product_id=product.id,
                quantity_snapshot=product.quantity,
                backend=settings.alert_backend.lower(),
                message_id=message_id,
            )
        )
        sent += 1

    db.commit()
    return sent, skipped
