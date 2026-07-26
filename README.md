# Kaizen Inventory Hub

Kaizen Inventory Hub is a FastAPI inventory and order-management application built for a DevOps deployment lab.

## Features

- Product catalog and SKU management
- Inventory adjustments with an audit trail
- Transactional order placement and stock deduction
- Low-stock dashboard, JSON API, and CSV report
- Console or Amazon SNS low-stock notifications
- SQLite locally and PostgreSQL in production
- Health, readiness, version, instance, and metrics endpoints
- Alembic migrations
- Docker and Docker Compose
- systemd web service and low-stock timer examples
- Automated tests

## Local quick start

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m app.seed
python -m pytest -q
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

- Application: http://127.0.0.1:8000
- Swagger API: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Readiness: http://127.0.0.1:8000/ready
- Metrics: http://127.0.0.1:8000/metrics

## Run the low-stock notifier

```bash
python -m app.notify_low_stock
```

The sample data includes products at or below their reorder levels, so the console backend prints alerts. Re-running within the configured cooldown skips duplicate notifications for unchanged quantities.

## Useful API examples

Create a product:

```bash
curl -X POST http://127.0.0.1:8000/api/products \
  -H 'Content-Type: application/json' \
  -d '{
    "sku": "MONITOR-27",
    "name": "27-inch Monitor",
    "description": "USB-C office monitor",
    "unit_price": "329.00",
    "quantity": 10,
    "reorder_level": 3
  }'
```

Create a multi-item order:

```bash
curl -X POST http://127.0.0.1:8000/api/orders \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_name": "Kaizen Academy",
    "customer_email": "orders@example.com",
    "items": [
      {"product_id": 1, "quantity": 1},
      {"product_id": 2, "quantity": 2}
    ]
  }'
```

## Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL and the web application, applies migrations, and seeds sample data.

## Production environment

Recommended production settings:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://inventory_app:PASSWORD@RDS_ENDPOINT:5432/inventory_hub
ALERT_BACKEND=sns
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:ACCOUNT_ID:inventory-low-stock
AWS_REGION=us-east-1
```

Use an EC2 IAM role for SNS access. Do not place static AWS access keys in `.env`.
