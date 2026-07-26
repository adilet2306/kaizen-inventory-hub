# Kaizen Inventory Hub on AWS
## End-to-End DevOps Deployment Lab

Kaizen Inventory Hub is a FastAPI inventory and order-management application designed for a complete DevOps deployment exercise.

Students first run and validate the application locally, deploy it manually to a single EC2 instance, and convert it into a systemd-managed Linux service. They then design the final AWS environment using PostgreSQL RDS, Amazon SNS, Secrets Manager, an Application Load Balancer, and an Auto Scaling Group.

The final architecture separates the scheduled low-stock process from the horizontally scaled web tier. Only one scheduler instance runs the low-stock systemd timer, preventing every web instance from sending the same SNS notification.

---

# 1. Validation Status

The following parts were validated during project development:

```text
Local SQLite migration:       Passed
Seed data:                    Passed
Dashboard and API startup:    Passed
Inventory workflow:           Passed
Order transaction tests:      Passed
Low-stock notifier:           Passed
Automated tests:              9 passed
Manual EC2 deployment:        Passed
systemd packaging issue:      Diagnosed and corrected
```

The RDS, SNS, ALB, ASG, and dedicated scheduler deployment sections are the final intended lab architecture. They are documented as reproducible deployment steps but were intentionally not executed during the shortened instructor walkthrough.

---

# 2. Application Features

Kaizen Inventory Hub includes:

- Product and SKU management
- Product descriptions and unit prices
- Inventory quantities and reorder thresholds
- Positive and negative stock adjustments
- Inventory movement audit history
- Customer order creation
- Transactional stock deductions
- Protection against negative stock
- Order detail and line-item views
- Low-stock dashboard
- Low-stock REST API
- Low-stock CSV export
- Console-based low-stock notifications
- Amazon SNS notification support
- Notification cooldown and duplicate suppression
- SQLite development support
- PostgreSQL production support
- Alembic migrations
- Swagger/OpenAPI documentation
- Health, readiness, version, instance, and metrics endpoints
- Docker and Docker Compose examples
- Gunicorn production server
- systemd web service
- systemd low-stock oneshot service
- systemd low-stock timer
- Automated tests

---

# 3. Important Endpoints

| Endpoint | Purpose |
|---|---|
| `/` | Inventory dashboard |
| `/products` | Product list |
| `/products/new` | Create a product |
| `/products/{id}` | Product details and inventory history |
| `/orders` | Order list |
| `/orders/new` | Create an order |
| `/orders/{id}` | Order details |
| `/reports/low-stock.csv` | Download low-stock CSV |
| `/api/products` | Product REST API |
| `/api/orders` | Order REST API |
| `/api/low-stock` | Low-stock REST API |
| `/health` | Confirms the web process responds |
| `/ready` | Confirms the database is reachable |
| `/version` | Application version and environment |
| `/instance` | Hostname and process information |
| `/metrics` | Basic Prometheus-style metrics |
| `/docs` | Swagger/OpenAPI interface |

---

# 4. Final AWS Architecture

```text
                                  Internet
                                     |
                                     v
                          Application Load Balancer
                       Public Subnet A + Public Subnet B
                                     |
                              HTTP port 8000
                                     |
                  +------------------+------------------+
                  |                                     |
                  v                                     v
          Web EC2 Instance A                    Web EC2 Instance B
          Gunicorn + FastAPI                    Gunicorn + FastAPI
                  |                                     |
                  +------------------+------------------+
                                     |
                                     v
                         PostgreSQL Amazon RDS
                    Private DB Subnet A + Subnet B

              Dedicated Scheduler EC2 Instance
                         systemd timer
                              |
                              +-------------> PostgreSQL RDS
                              |
                              +-------------> Amazon SNS Topic
                                                   |
                                                   v
                                          Email subscription
```

Supporting services:

```text
Custom VPC
Internet Gateway
Public and private route tables
Security groups
DB subnet group
AWS Secrets Manager
EC2 IAM instance profile
Web Launch Template
Scheduler Launch Template
Target Group
Application Load Balancer
Web Auto Scaling Group
```

## Why use a dedicated scheduler?

The web tier has multiple Auto Scaling instances. If every web instance ran the low-stock timer, two or more instances could evaluate the same low-stock products at nearly the same time.

The application stores a notification cooldown record in PostgreSQL, which reduces duplicates, but two concurrent scheduler processes could still race before either transaction commits.

Therefore:

```text
Web ASG instances:       web service only
Scheduler instance:      low-stock timer only
```

---

# 5. Learning Objectives

Students should be able to:

1. Run a FastAPI application locally.
2. Use a Python virtual environment.
3. Configure an application with environment variables.
4. Apply Alembic migrations.
5. Seed initial relational data.
6. Test a web UI and REST API.
7. Deploy an application manually to EC2.
8. Create dedicated Linux service users.
9. Store application code under `/opt`.
10. Store configuration under `/etc`.
11. Store persistent data under `/var/lib`.
12. Run Gunicorn through systemd.
13. Run scheduled jobs through a systemd timer.
14. Diagnose Linux file-permission and application-startup errors.
15. Replace SQLite with PostgreSQL RDS.
16. Configure SNS application notifications.
17. Use an EC2 IAM role instead of static AWS keys.
18. Store production configuration in Secrets Manager.
19. Bootstrap clean EC2 instances with user data.
20. Create a Launch Template.
21. Create an Application Load Balancer.
22. Create an Auto Scaling Group.
23. Verify shared state across multiple web instances.
24. Test automatic instance replacement.
25. Separate scheduled jobs from a horizontally scaled web tier.

---

# 6. Prerequisites

Students need:

- An AWS account
- AWS Console permissions
- A GitHub account
- Git installed locally
- Python 3.11 or newer
- An SSH client
- An EC2 key pair
- Basic Linux, Git, and AWS knowledge
- The Kaizen Inventory Hub source package

Extract:

```bash
unzip kaizen-inventory-hub-v1.0.0.zip
cd kaizen-inventory-hub
```

---

# 7. Repository Safety

The repository must not contain:

```text
.env
.venv/
instance/
SQLite database files
AWS credentials
Database passwords
Secrets Manager values
```

Recommended `.gitignore`:

```gitignore
.env
.env.*
!.env.example

.venv/
venv/

instance/
*.db
*.sqlite
*.sqlite3

__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/

.DS_Store
.idea/
.vscode/
```

Before pushing:

```bash
git status --ignored
```

---

# 8. Application Configuration

The included `.env.example` contains:

```dotenv
APP_NAME=Kaizen Inventory Hub
APP_ENV=development
APP_VERSION=1.0.0
SECRET_KEY=change-me
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

DATABASE_URL=sqlite:///./instance/inventory.db

ALERT_BACKEND=console
SNS_TOPIC_ARN=
AWS_REGION=us-east-1
LOW_STOCK_COOLDOWN_MINUTES=60

METRICS_ENABLED=true
```

The configuration module exports:

```python
Settings
get_settings()
```

Validate configuration with:

```bash
python -c \
  'from app.config import get_settings; s = get_settings(); print(s.app_name, s.app_env, s.database_url, s.alert_backend)'
```

---

# 9. Phase 1 — Local Deployment

## 9.1 Create local configuration

```bash
cp .env.example .env
chmod 600 .env
```

Generate a secret:

```bash
python3 -c \
  'import secrets; print(secrets.token_urlsafe(32))'
```

Place the result in:

```dotenv
SECRET_KEY=PASTE_GENERATED_VALUE
```

## 9.2 Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Verify:

```bash
which python
python --version
```

## 9.3 Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 9.4 Apply migration

```bash
python -m alembic upgrade head
```

Verify:

```bash
python -m alembic current
```

## 9.5 Seed products

```bash
python -m app.seed
```

Expected:

```text
Created three sample products
```

Running it again should return:

```text
Seed skipped: products already exist
```

The seed creates:

| SKU | Product | Quantity | Reorder level |
|---|---|---:|---:|
| `LAPTOP-14` | KaizenBook 14 | 12 | 4 |
| `DOCK-USBC` | USB-C Dock | 5 | 5 |
| `HEADSET-01` | Training Headset | 2 | 6 |

## 9.6 Run tests

```bash
python -m pytest -q
```

Expected:

```text
9 passed
```

## 9.7 Start the application

```bash
python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

Open:

```text
Application: http://127.0.0.1:8000
Swagger:     http://127.0.0.1:8000/docs
```

## 9.8 Test health endpoints

```bash
curl -s http://127.0.0.1:8000/health
echo

curl -s http://127.0.0.1:8000/ready
echo

curl -s http://127.0.0.1:8000/version
echo

curl -s http://127.0.0.1:8000/instance
echo

curl -s http://127.0.0.1:8000/metrics
```

## 9.9 Test the workflow

1. Review the three sample products.
2. Create a product.
3. Add inventory.
4. Remove inventory.
5. Review inventory movement history.
6. Create an order.
7. Confirm stock decreases.
8. Attempt an order larger than available stock.
9. Confirm the order is rejected.
10. Open the low-stock report.
11. Download the low-stock CSV.

Example product:

```text
SKU: MONITOR-27
Name: 27-inch Monitor
Description: USB-C office monitor
Unit price: 329.00
Quantity: 10
Reorder level: 3
```

## 9.10 Run the low-stock notifier

```bash
python -m app.notify_low_stock
```

Expected:

```text
Low stock: HEADSET-01 - Training Headset
Current quantity: 2
Reorder level: 6

Low stock: DOCK-USBC - USB-C Dock
Current quantity: 5
Reorder level: 5

Low-stock notification run complete: sent=2 skipped=0
```

Run it again during the cooldown:

```bash
python -m app.notify_low_stock
```

Expected:

```text
Low-stock notification run complete: sent=0 skipped=2
```

---

# 10. Phase 2 — Manual Single-EC2 Deployment

This phase uses:

```text
One EC2 instance
SQLite
Console notifications
Manual Uvicorn process
```

## 10.1 Push to GitHub

Create an empty repository:

```text
kaizen-inventory-hub
```

Then:

```bash
git init
git branch -M main

git add .
git commit -m "Initial Kaizen Inventory Hub application"

git remote add origin \
  https://github.com/YOUR_GITHUB_USERNAME/kaizen-inventory-hub.git

git push -u origin main
```

## 10.2 Launch EC2

| Setting | Value |
|---|---|
| Name | `kaizen-inventory-test` |
| AMI | Ubuntu Server 24.04 LTS |
| Architecture | x86_64 |
| Instance type | `t3.small` |
| Public IPv4 | Enabled |
| Storage | 16 GiB gp3 |

Temporary inbound rules:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your current IP `/32` |
| Custom TCP | 8000 | Your current IP `/32` |

## 10.3 Connect

```bash
chmod 400 ~/Downloads/YOUR_KEY.pem

ssh \
  -i ~/Downloads/YOUR_KEY.pem \
  ubuntu@EC2_PUBLIC_IP
```

## 10.4 Install dependencies

```bash
sudo apt-get update

sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  curl \
  sqlite3
```

## 10.5 Clone and configure

```bash
cd ~

git clone \
  https://github.com/YOUR_GITHUB_USERNAME/kaizen-inventory-hub.git

cd kaizen-inventory-hub

cp .env.example .env
chmod 600 .env
```

Use:

```dotenv
APP_NAME=Kaizen Inventory Hub
APP_ENV=development
APP_VERSION=1.0.0
SECRET_KEY=PASTE_GENERATED_SECRET
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

DATABASE_URL=sqlite:///./instance/inventory.db

ALERT_BACKEND=console
SNS_TOPIC_ARN=
AWS_REGION=us-east-1
LOW_STOCK_COOLDOWN_MINUTES=60

METRICS_ENABLED=true
```

## 10.6 Install application

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m alembic upgrade head
python -m app.seed
python -m pytest -q
```

## 10.7 Run

```bash
python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000
```

Open:

```text
http://EC2_PUBLIC_IP:8000
```

---

# 11. Phase 3 — Production-Style Linux Layout

Use:

```text
Application code: /opt/kaizen-inventory-hub
Configuration:    /etc/kaizen-inventory-hub/inventory.env
Persistent data:  /var/lib/kaizen-inventory-hub
```

Create:

```text
kaizen-inventory-web.service
kaizen-inventory-low-stock.service
kaizen-inventory-low-stock.timer
```

## 11.1 Stop Uvicorn

```text
Ctrl+C
```

Confirm:

```bash
sudo ss -lntp | grep 8000
```

## 11.2 Create service user

```bash
getent group inventory >/dev/null ||
  sudo groupadd --system inventory

id inventory >/dev/null 2>&1 ||
  sudo useradd \
    --system \
    --gid inventory \
    --home-dir /opt/kaizen-inventory-hub \
    --shell /usr/sbin/nologin \
    inventory
```

## 11.3 Copy code

```bash
sudo cp -a \
  ~/kaizen-inventory-hub \
  /opt/kaizen-inventory-hub

sudo rm -rf \
  /opt/kaizen-inventory-hub/.git \
  /opt/kaizen-inventory-hub/.venv \
  /opt/kaizen-inventory-hub/.env \
  /opt/kaizen-inventory-hub/instance
```

## 11.4 Create virtual environment

```bash
sudo python3 -m venv \
  /opt/kaizen-inventory-hub/.venv

sudo /opt/kaizen-inventory-hub/.venv/bin/python \
  -m pip install --upgrade pip

sudo /opt/kaizen-inventory-hub/.venv/bin/python \
  -m pip install \
  -r /opt/kaizen-inventory-hub/requirements.txt
```

## 11.5 Move SQLite data

```bash
sudo mkdir -p \
  /var/lib/kaizen-inventory-hub

sudo cp \
  ~/kaizen-inventory-hub/instance/inventory.db \
  /var/lib/kaizen-inventory-hub/inventory.db

sudo chown -R \
  inventory:inventory \
  /var/lib/kaizen-inventory-hub

sudo chmod 750 \
  /var/lib/kaizen-inventory-hub
```

## 11.6 Create environment file

```bash
sudo mkdir -p \
  /etc/kaizen-inventory-hub

sudo cp \
  ~/kaizen-inventory-hub/.env \
  /etc/kaizen-inventory-hub/inventory.env
```

Use:

```dotenv
APP_NAME="Kaizen Inventory Hub"
APP_ENV=production
APP_VERSION=1.0.0
SECRET_KEY=YOUR_GENERATED_SECRET
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

DATABASE_URL=sqlite:////var/lib/kaizen-inventory-hub/inventory.db

ALERT_BACKEND=console
SNS_TOPIC_ARN=
AWS_REGION=us-east-1
LOW_STOCK_COOLDOWN_MINUTES=60

METRICS_ENABLED=true
WEB_CONCURRENCY=1
```

The absolute SQLite URL requires four slashes:

```text
sqlite:////var/lib/kaizen-inventory-hub/inventory.db
```

Protect it:

```bash
sudo chown \
  root:inventory \
  /etc/kaizen-inventory-hub/inventory.env

sudo chmod 640 \
  /etc/kaizen-inventory-hub/inventory.env

sudo ln -sfn \
  /etc/kaizen-inventory-hub/inventory.env \
  /opt/kaizen-inventory-hub/.env
```

Set code permissions:

```bash
sudo chown -R root:root \
  /opt/kaizen-inventory-hub

sudo chmod -R a+rX \
  /opt/kaizen-inventory-hub
```

## 11.7 Important SQLite path fix

`app/database.py` must create the parent directory of the configured SQLite file, not always create `/opt/kaizen-inventory-hub/instance`.

Correct implementation:

```python
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import PROJECT_ROOT, get_settings

settings = get_settings()


def ensure_sqlite_parent(database_url: str) -> None:
    """Create the parent directory for file-backed SQLite databases."""
    if not database_url.startswith("sqlite:///"):
        return

    database_path = database_url.removeprefix("sqlite:///")

    if not database_path or database_path == ":memory:":
        return

    path = Path(database_path)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    path.parent.mkdir(parents=True, exist_ok=True)


ensure_sqlite_parent(settings.database_url)

engine_kwargs: dict[str, object] = {
    "pool_pre_ping": True,
}

if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
    }

engine = create_engine(
    settings.database_url,
    **engine_kwargs,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
```

Without this fix, the `inventory` service user may receive a permission error while trying to create:

```text
/opt/kaizen-inventory-hub/instance
```

Symptoms:

```text
Gunicorn exits with status 3
Low-stock oneshot service fails
Web service remains activating/auto-restart
```

## 11.8 Validate

```bash
cd /opt/kaizen-inventory-hub

sudo -u inventory \
  /opt/kaizen-inventory-hub/.venv/bin/python \
  -c 'from app.config import get_settings; s = get_settings(); print(s.app_name, s.app_env, s.database_url, s.alert_backend)'
```

Expected:

```text
Kaizen Inventory Hub production sqlite:////var/lib/kaizen-inventory-hub/inventory.db console
```

Verify database engine:

```bash
sudo -u inventory \
  /opt/kaizen-inventory-hub/.venv/bin/python \
  -c 'from app.database import engine; print(engine.url)'
```

Apply migration:

```bash
sudo -u inventory \
  /opt/kaizen-inventory-hub/.venv/bin/python \
  -m alembic upgrade head
```

---

# 12. systemd Web Service

Create:

```bash
sudo tee \
  /etc/systemd/system/kaizen-inventory-web.service \
  >/dev/null <<'EOF'
[Unit]
Description=Kaizen Inventory Hub Web Service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=inventory
Group=inventory
WorkingDirectory=/opt/kaizen-inventory-hub
EnvironmentFile=/etc/kaizen-inventory-hub/inventory.env

ExecStart=/opt/kaizen-inventory-hub/.venv/bin/gunicorn \
  -c /opt/kaizen-inventory-hub/gunicorn.conf.py \
  app.main:app

Restart=always
RestartSec=5
TimeoutStopSec=30

StandardOutput=journal
StandardError=journal

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

---

# 13. systemd Low-Stock Service

Create:

```bash
sudo tee \
  /etc/systemd/system/kaizen-inventory-low-stock.service \
  >/dev/null <<'EOF'
[Unit]
Description=Kaizen Inventory Hub Low-Stock Check
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=inventory
Group=inventory
WorkingDirectory=/opt/kaizen-inventory-hub
EnvironmentFile=/etc/kaizen-inventory-hub/inventory.env

ExecStart=/opt/kaizen-inventory-hub/.venv/bin/python \
  -m app.notify_low_stock

StandardOutput=journal
StandardError=journal

NoNewPrivileges=true
PrivateTmp=true
EOF
```

---

# 14. systemd Low-Stock Timer

For the lab, use 15 minutes:

```bash
sudo tee \
  /etc/systemd/system/kaizen-inventory-low-stock.timer \
  >/dev/null <<'EOF'
[Unit]
Description=Run Kaizen Inventory Low-Stock Check Every 15 Minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
Unit=kaizen-inventory-low-stock.service

[Install]
WantedBy=timers.target
EOF
```

Enable:

```bash
sudo systemctl daemon-reload

sudo systemctl enable --now \
  kaizen-inventory-web

sudo systemctl enable --now \
  kaizen-inventory-low-stock.timer
```

Verify:

```bash
sudo systemctl is-active \
  kaizen-inventory-web \
  kaizen-inventory-low-stock.timer

systemctl list-timers \
  kaizen-inventory-low-stock.timer
```

Manually run:

```bash
sudo systemctl start \
  kaizen-inventory-low-stock.service

sudo journalctl \
  -u kaizen-inventory-low-stock.service \
  -n 100 \
  --no-pager
```

A successful oneshot service becomes:

```text
inactive (dead)
```

with:

```text
Result=success
ExecMainStatus=0
```

---

# 15. Phase 4 — Final AWS Network

Use:

```text
Region: us-east-1
VPC CIDR: 10.40.0.0/16
```

## 15.1 VPC

Create:

```text
kaizen-inventory-vpc
```

Enable:

```text
DNS resolution
DNS hostnames
```

## 15.2 Public subnets

| Name | CIDR | Availability Zone |
|---|---|---|
| `kaizen-inventory-public-a` | `10.40.1.0/24` | First AZ |
| `kaizen-inventory-public-b` | `10.40.2.0/24` | Second AZ |

Enable automatic public IPv4 assignment for the lab.

## 15.3 Private DB subnets

| Name | CIDR | Availability Zone |
|---|---|---|
| `kaizen-inventory-private-db-a` | `10.40.11.0/24` | First AZ |
| `kaizen-inventory-private-db-b` | `10.40.12.0/24` | Second AZ |

Do not assign public IPv4 addresses.

## 15.4 Internet Gateway

Create:

```text
kaizen-inventory-igw
```

Attach to the VPC.

## 15.5 Public route table

Create:

```text
kaizen-inventory-public-rt
```

Route:

```text
0.0.0.0/0 → kaizen-inventory-igw
```

Associate both public subnets.

## 15.6 Private DB route table

Create:

```text
kaizen-inventory-private-db-rt
```

Keep only the local VPC route.

Associate both private DB subnets.

---

# 16. Security Groups

## 16.1 ALB security group

Name:

```text
kaizen-inventory-alb-sg
```

Inbound:

| Type | Port | Source |
|---|---:|---|
| HTTP | 80 | `0.0.0.0/0` |

## 16.2 Application security group

Name:

```text
kaizen-inventory-app-sg
```

Inbound:

| Type | Port | Source |
|---|---:|---|
| Custom TCP | 8000 | `kaizen-inventory-alb-sg` |
| SSH | 22 | Your current public IP `/32` |
| Custom TCP | 8000 | Your current public IP `/32`, temporary |

## 16.3 Scheduler security group

Name:

```text
kaizen-inventory-scheduler-sg
```

Inbound:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your current public IP `/32` |

The scheduler does not receive web traffic.

## 16.4 RDS security group

Name:

```text
kaizen-inventory-rds-sg
```

Inbound:

| Type | Port | Source |
|---|---:|---|
| PostgreSQL | 5432 | `kaizen-inventory-app-sg` |
| PostgreSQL | 5432 | `kaizen-inventory-scheduler-sg` |

Never permit PostgreSQL from:

```text
0.0.0.0/0
```

---

# 17. Phase 5 — PostgreSQL RDS

## 17.1 DB subnet group

Create:

```text
kaizen-inventory-db-subnet-group
```

Select:

```text
kaizen-inventory-private-db-a
kaizen-inventory-private-db-b
```

## 17.2 RDS instance

| Setting | Value |
|---|---|
| Engine | PostgreSQL |
| Identifier | `kaizen-inventory-db` |
| Master username | `inventory_admin` |
| Instance class | Smallest suitable burstable class |
| Storage | 20 GiB gp3 |
| VPC | `kaizen-inventory-vpc` |
| DB subnet group | `kaizen-inventory-db-subnet-group` |
| Public access | No |
| Security group | `kaizen-inventory-rds-sg` |
| Port | 5432 |
| Multi-AZ | No for this lab |

Generate a master password:

```bash
openssl rand -hex 18
```

Copy the endpoint after the database becomes available.

---

# 18. Create PostgreSQL Database and App User

Launch a temporary admin EC2 instance:

| Setting | Value |
|---|---|
| Name | `kaizen-inventory-db-admin` |
| VPC | `kaizen-inventory-vpc` |
| Subnet | `kaizen-inventory-public-a` |
| Public IP | Enabled |
| Security group | `kaizen-inventory-app-sg` |

Install the PostgreSQL client:

```bash
sudo apt-get update
sudo apt-get install -y postgresql-client
```

Connect to the default database:

```bash
psql \
  -h RDS_ENDPOINT \
  -U inventory_admin \
  -d postgres \
  -W
```

Generate an application password:

```bash
openssl rand -hex 18
```

Create the app user:

```sql
CREATE USER inventory_app
WITH PASSWORD 'APP_DATABASE_PASSWORD';
```

Create the database:

```sql
CREATE DATABASE kaizen_inventory;
```

Connect:

```sql
\c kaizen_inventory
```

Grant:

```sql
GRANT CONNECT
ON DATABASE kaizen_inventory
TO inventory_app;

GRANT USAGE, CREATE
ON SCHEMA public
TO inventory_app;
```

Exit:

```sql
\q
```

Test:

```bash
psql \
  -h RDS_ENDPOINT \
  -U inventory_app \
  -d kaizen_inventory \
  -W \
  -c 'SELECT current_user, current_database();'
```

Expected:

```text
inventory_app | kaizen_inventory
```

Test table creation:

```bash
psql \
  -h RDS_ENDPOINT \
  -U inventory_app \
  -d kaizen_inventory \
  -W \
  -c 'CREATE TABLE permission_test (id integer); DROP TABLE permission_test;'
```

---

# 19. Phase 6 — Amazon SNS

Create a Standard topic:

```text
kaizen-inventory-low-stock
```

Copy its ARN:

```text
arn:aws:sns:us-east-1:ACCOUNT_ID:kaizen-inventory-low-stock
```

Create a subscription:

| Setting | Value |
|---|---|
| Protocol | Email |
| Endpoint | Instructor or student email |

Open the confirmation email and confirm the subscription.

The application sends messages similar to:

```text
Subject: Low stock: HEADSET-01

Low stock: HEADSET-01 - Training Headset
Current quantity: 2
Reorder level: 6
```

---

# 20. Phase 7 — EC2 IAM Role

Create:

```text
kaizen-inventory-ec2-role
```

Trusted service:

```text
EC2
```

Create inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadProductionSecret",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:kaizen-inventory/production-*"
    },
    {
      "Sid": "PublishLowStockNotifications",
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:us-east-1:ACCOUNT_ID:kaizen-inventory-low-stock"
    }
  ]
}
```

The web instances receive the same role for simplicity, although only the scheduler publishes SNS messages.

Do not create static AWS access keys.

---

# 21. Phase 8 — Secrets Manager

Create:

```text
kaizen-inventory/production
```

Store:

| Key | Value |
|---|---|
| `APP_NAME` | `Kaizen Inventory Hub` |
| `APP_ENV` | `production` |
| `APP_VERSION` | `1.0.0` |
| `SECRET_KEY` | Generated value |
| `HOST` | `0.0.0.0` |
| `PORT` | `8000` |
| `LOG_LEVEL` | `INFO` |
| `DATABASE_URL` | PostgreSQL URL |
| `ALERT_BACKEND` | `sns` |
| `SNS_TOPIC_ARN` | SNS topic ARN |
| `AWS_REGION` | `us-east-1` |
| `LOW_STOCK_COOLDOWN_MINUTES` | `60` |
| `METRICS_ENABLED` | `true` |
| `WEB_CONCURRENCY` | `2` |

Generate:

```bash
python3 -c \
  'import secrets; print(secrets.token_urlsafe(48))'
```

Database URL:

```text
postgresql+psycopg://inventory_app:APP_PASSWORD@RDS_ENDPOINT:5432/kaizen_inventory
```

A hexadecimal database password avoids URL-encoding problems.

---

# 22. Phase 9 — Bootstrap Script

Add:

```text
deploy/bootstrap-node.sh
```

This script supports:

```text
NODE_ROLE=web
NODE_ROLE=scheduler
```

Create:

```bash
cat > deploy/bootstrap-node.sh <<'BASH'
#!/bin/bash

set -euo pipefail

NODE_ROLE="${NODE_ROLE:?NODE_ROLE must be web or scheduler}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SECRET_ID="${SECRET_ID:-kaizen-inventory/production}"

APP_USER="inventory"
APP_GROUP="inventory"
APP_DIR="/opt/kaizen-inventory-hub"
ENV_DIR="/etc/kaizen-inventory-hub"
ENV_FILE="${ENV_DIR}/inventory.env"

case "${NODE_ROLE}" in
  web|scheduler)
    ;;
  *)
    echo "Unsupported NODE_ROLE=${NODE_ROLE}"
    exit 1
    ;;
esac

ARCH="$(uname -m)"

case "${ARCH}" in
  x86_64)
    AWSCLI_ARCH="x86_64"
    ;;
  aarch64|arm64)
    AWSCLI_ARCH="aarch64"
    ;;
  *)
    echo "Unsupported architecture: ${ARCH}"
    exit 1
    ;;
esac

rm -rf /tmp/aws /tmp/awscliv2.zip

curl \
  --fail \
  --silent \
  --show-error \
  --location \
  "https://awscli.amazonaws.com/awscli-exe-linux-${AWSCLI_ARCH}.zip" \
  --output /tmp/awscliv2.zip

unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install --update

rm -rf /tmp/aws /tmp/awscliv2.zip

if ! getent group "${APP_GROUP}" >/dev/null; then
  groupadd --system "${APP_GROUP}"
fi

if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd \
    --system \
    --gid "${APP_GROUP}" \
    --home-dir "${APP_DIR}" \
    --shell /usr/sbin/nologin \
    "${APP_USER}"
fi

python3 -m venv "${APP_DIR}/.venv"

"${APP_DIR}/.venv/bin/python" \
  -m pip install --upgrade pip

"${APP_DIR}/.venv/bin/python" \
  -m pip install \
  -r "${APP_DIR}/requirements.txt"

install \
  -d \
  -m 0750 \
  -o root \
  -g "${APP_GROUP}" \
  "${ENV_DIR}"

SECRET_JSON="$(
  aws secretsmanager get-secret-value \
    --secret-id "${SECRET_ID}" \
    --region "${AWS_REGION}" \
    --query SecretString \
    --output text
)"

export SECRET_JSON
export ENV_FILE

python3 <<'PYTHON'
import json
import os
import shlex
from pathlib import Path

keys = [
    "APP_NAME",
    "APP_ENV",
    "APP_VERSION",
    "SECRET_KEY",
    "HOST",
    "PORT",
    "LOG_LEVEL",
    "DATABASE_URL",
    "ALERT_BACKEND",
    "SNS_TOPIC_ARN",
    "AWS_REGION",
    "LOW_STOCK_COOLDOWN_MINUTES",
    "METRICS_ENABLED",
    "WEB_CONCURRENCY",
]

secret = json.loads(os.environ["SECRET_JSON"])

missing = [
    key
    for key in keys
    if str(secret.get(key, "")).strip() == ""
]

if missing:
    raise RuntimeError(
        "Missing required secret keys: " + ", ".join(missing)
    )

path = Path(os.environ["ENV_FILE"])

with path.open("w", encoding="utf-8") as file:
    for key in keys:
        file.write(
            f"{key}={shlex.quote(str(secret[key]))}\n"
        )
PYTHON

unset SECRET_JSON

chown "root:${APP_GROUP}" "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"

ln -sfn \
  "${ENV_FILE}" \
  "${APP_DIR}/.env"

chown -R root:root "${APP_DIR}"
chmod -R a+rX "${APP_DIR}"

cat > /etc/systemd/system/kaizen-inventory-web.service <<'SERVICE'
[Unit]
Description=Kaizen Inventory Hub Web Service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=inventory
Group=inventory
WorkingDirectory=/opt/kaizen-inventory-hub
EnvironmentFile=/etc/kaizen-inventory-hub/inventory.env

ExecStart=/opt/kaizen-inventory-hub/.venv/bin/gunicorn \
  -c /opt/kaizen-inventory-hub/gunicorn.conf.py \
  app.main:app

Restart=always
RestartSec=5
TimeoutStopSec=30

StandardOutput=journal
StandardError=journal

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE

cat > /etc/systemd/system/kaizen-inventory-low-stock.service <<'SERVICE'
[Unit]
Description=Kaizen Inventory Hub Low-Stock SNS Check
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=inventory
Group=inventory
WorkingDirectory=/opt/kaizen-inventory-hub
EnvironmentFile=/etc/kaizen-inventory-hub/inventory.env

ExecStart=/opt/kaizen-inventory-hub/.venv/bin/python \
  -m app.notify_low_stock

StandardOutput=journal
StandardError=journal

NoNewPrivileges=true
PrivateTmp=true
SERVICE

cat > /etc/systemd/system/kaizen-inventory-low-stock.timer <<'TIMER'
[Unit]
Description=Run Kaizen Inventory Low-Stock SNS Check Every 15 Minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
Unit=kaizen-inventory-low-stock.service

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload

if [[ "${NODE_ROLE}" == "web" ]]; then
  systemctl disable --now \
    kaizen-inventory-low-stock.timer \
    >/dev/null 2>&1 || true

  systemctl enable --now \
    kaizen-inventory-web

  for attempt in $(seq 1 60); do
    if curl \
      --fail \
      --silent \
      http://127.0.0.1:8000/health \
      >/dev/null; then

      echo "Web node is healthy"
      exit 0
    fi

    echo "Web health attempt ${attempt}/60 failed"
    sleep 5
  done

  journalctl \
    -u kaizen-inventory-web \
    -n 100 \
    --no-pager || true

  exit 1
fi

systemctl disable --now \
  kaizen-inventory-web \
  >/dev/null 2>&1 || true

systemctl enable --now \
  kaizen-inventory-low-stock.timer

systemctl start \
  kaizen-inventory-low-stock.service

echo "Scheduler node configured"
BASH
```

Validate:

```bash
chmod +x deploy/bootstrap-node.sh
bash -n deploy/bootstrap-node.sh
```

---

# 23. Web User Data

Create:

```text
deploy/aws-web-user-data.sh
```

```bash
#!/bin/bash

set -euo pipefail

exec > >(
  tee /var/log/kaizen-inventory-bootstrap.log |
  logger -t kaizen-inventory-user-data -s 2>/dev/console
) 2>&1

APP_DIR="/opt/kaizen-inventory-hub"
REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/kaizen-inventory-hub.git"
GIT_BRANCH="main"

export DEBIAN_FRONTEND=noninteractive

apt-get update

apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  curl \
  unzip

rm -rf "${APP_DIR}"

git clone \
  --branch "${GIT_BRANCH}" \
  --depth 1 \
  "${REPO_URL}" \
  "${APP_DIR}"

NODE_ROLE="web" \
AWS_REGION="us-east-1" \
SECRET_ID="kaizen-inventory/production" \
"${APP_DIR}/deploy/bootstrap-node.sh"
```

---

# 24. Scheduler User Data

Create:

```text
deploy/aws-scheduler-user-data.sh
```

```bash
#!/bin/bash

set -euo pipefail

exec > >(
  tee /var/log/kaizen-inventory-bootstrap.log |
  logger -t kaizen-inventory-user-data -s 2>/dev/console
) 2>&1

APP_DIR="/opt/kaizen-inventory-hub"
REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/kaizen-inventory-hub.git"
GIT_BRANCH="main"

export DEBIAN_FRONTEND=noninteractive

apt-get update

apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  curl \
  unzip

rm -rf "${APP_DIR}"

git clone \
  --branch "${GIT_BRANCH}" \
  --depth 1 \
  "${REPO_URL}" \
  "${APP_DIR}"

NODE_ROLE="scheduler" \
AWS_REGION="us-east-1" \
SECRET_ID="kaizen-inventory/production" \
"${APP_DIR}/deploy/bootstrap-node.sh"
```

Validate and push:

```bash
chmod +x \
  deploy/aws-web-user-data.sh \
  deploy/aws-scheduler-user-data.sh

bash -n deploy/aws-web-user-data.sh
bash -n deploy/aws-scheduler-user-data.sh

git add deploy/

git commit \
  -m "Add AWS web and scheduler bootstrap"

git push
```

---

# 25. Phase 10 — Web Launch Template

Create:

```text
kaizen-inventory-web-launch-template
```

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 |
| Architecture | x86_64 |
| Instance type | `t3.small` |
| Security group | `kaizen-inventory-app-sg` |
| IAM instance profile | `kaizen-inventory-ec2-role` |
| Storage | 16 GiB gp3 |
| User data | `deploy/aws-web-user-data.sh` |

Do not select a fixed subnet.

---

# 26. Validate One Web Template Instance

Launch:

```text
kaizen-inventory-web-template-test
```

Use:

```text
VPC: kaizen-inventory-vpc
Subnet: kaizen-inventory-public-a
```

Wait:

```bash
sudo cloud-init status --wait
```

Verify:

```bash
sudo systemctl is-active \
  kaizen-inventory-web

sudo systemctl is-enabled \
  kaizen-inventory-low-stock.timer
```

Expected:

```text
active
disabled
```

Verify IAM:

```bash
aws sts get-caller-identity
```

## 26.1 Run migration once

```bash
cd /opt/kaizen-inventory-hub

sudo -u inventory \
  /opt/kaizen-inventory-hub/.venv/bin/python \
  -m alembic upgrade head
```

Seed:

```bash
sudo -u inventory \
  /opt/kaizen-inventory-hub/.venv/bin/python \
  -m app.seed
```

Restart:

```bash
sudo systemctl restart \
  kaizen-inventory-web
```

Test:

```bash
curl -s http://127.0.0.1:8000/ready
echo
```

Expected:

```json
{"status":"ready","database":"connected"}
```

Open temporarily:

```text
http://WEB_TEMPLATE_TEST_PUBLIC_IP:8000
```

---

# 27. Phase 11 — Target Group

Create:

```text
kaizen-inventory-tg
```

| Setting | Value |
|---|---|
| Target type | Instances |
| Protocol | HTTP |
| Port | 8000 |
| VPC | `kaizen-inventory-vpc` |
| Protocol version | HTTP1 |

Health check:

| Setting | Value |
|---|---|
| Path | `/health` |
| Port | Traffic port |
| Success code | 200 |
| Healthy threshold | 2 |
| Unhealthy threshold | 2 |
| Timeout | 5 seconds |
| Interval | 15 seconds |

Do not manually register the template-test instance.

---

# 28. Phase 12 — Application Load Balancer

Create:

```text
kaizen-inventory-alb
```

| Setting | Value |
|---|---|
| Scheme | Internet-facing |
| IP type | IPv4 |
| VPC | `kaizen-inventory-vpc` |
| Subnets | Both public subnets |
| Security group | `kaizen-inventory-alb-sg` |

Listener:

| Protocol | Port | Action |
|---|---:|---|
| HTTP | 80 | Forward to `kaizen-inventory-tg` |

---

# 29. Phase 13 — Web Auto Scaling Group

Create:

```text
kaizen-inventory-web-asg
```

Use:

```text
kaizen-inventory-web-launch-template
```

Subnets:

```text
kaizen-inventory-public-a
kaizen-inventory-public-b
```

Attach:

```text
kaizen-inventory-tg
```

Enable:

```text
Elastic Load Balancing health checks
```

Grace period:

```text
600 seconds
```

Capacity:

| Setting | Value |
|---|---:|
| Minimum | 2 |
| Desired | 2 |
| Maximum | 4 |

For this lab:

```text
No scaling policy
No CloudWatch alarms
No centralized logging
```

Wait for:

```text
2 Healthy
```

---

# 30. Phase 14 — Scheduler Launch Template

Create:

```text
kaizen-inventory-scheduler-launch-template
```

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 |
| Architecture | x86_64 |
| Instance type | `t3.micro` or `t3.small` |
| Security group | `kaizen-inventory-scheduler-sg` |
| IAM instance profile | `kaizen-inventory-ec2-role` |
| Storage | 12–16 GiB gp3 |
| User data | `deploy/aws-scheduler-user-data.sh` |

Launch one instance:

```text
kaizen-inventory-scheduler
```

Use either public subnet for this simplified lab.

Verify:

```bash
sudo cloud-init status --wait

sudo systemctl is-active \
  kaizen-inventory-low-stock.timer

sudo systemctl is-enabled \
  kaizen-inventory-web
```

Expected:

```text
active
disabled
```

Check the scheduled job:

```bash
systemctl list-timers \
  kaizen-inventory-low-stock.timer
```

Manually run:

```bash
sudo systemctl start \
  kaizen-inventory-low-stock.service
```

Logs:

```bash
sudo journalctl \
  -u kaizen-inventory-low-stock.service \
  -n 100 \
  --no-pager
```

Confirm the subscribed email receives an SNS notification.

---

# 31. Validate the Final Environment

Set:

```bash
ALB_DNS="YOUR_ALB_DNS_NAME"
```

Test:

```bash
curl -s "http://${ALB_DNS}/health"
echo

curl -s "http://${ALB_DNS}/ready"
echo
```

Test multiple web hosts:

```bash
for i in {1..20}; do
  curl -s "http://${ALB_DNS}/instance"
  echo
  sleep 1
done
```

Open:

```text
http://ALB_DNS_NAME
```

Validate:

1. Seed products exist.
2. Create a product.
3. Refresh repeatedly.
4. The product remains regardless of the responding instance.
5. Adjust stock.
6. Create an order.
7. Confirm stock changes persist.
8. Confirm orders appear through either web instance.
9. Reduce a product below its reorder threshold.
10. Run the scheduler service.
11. Confirm SNS email delivery.

This verifies:

```text
Shared application state:       PostgreSQL RDS
Web traffic distribution:       ALB
Web instance lifecycle:         ASG
Scheduled low-stock processing: Dedicated scheduler
External notification delivery: SNS
Configuration delivery:         Secrets Manager
AWS authentication:             EC2 IAM role
```

---

# 32. Remove Temporary Direct Access

Remove:

```text
TCP 8000 → Your current public IP/32
```

from:

```text
kaizen-inventory-app-sg
```

Keep:

```text
TCP 8000 → kaizen-inventory-alb-sg
SSH 22 → Your current public IP/32
```

Direct access should fail:

```text
http://EC2_PUBLIC_IP:8000
```

ALB access should work:

```text
http://ALB_DNS_NAME
```

---

# 33. Test Auto Scaling Replacement

Terminate one ASG-managed web instance.

Expected:

1. The other web instance keeps serving traffic.
2. ASG launches a replacement.
3. User data installs and starts the application.
4. The new instance registers with the target group.
5. The target group returns to two healthy targets.
6. Products and orders remain because they are stored in RDS.
7. The scheduler remains unaffected.

---

# 34. Cleanup Temporary Resources

Terminate:

```text
kaizen-inventory-test
kaizen-inventory-db-admin
kaizen-inventory-web-template-test
```

Keep:

```text
Two ASG-managed web instances
One scheduler instance
PostgreSQL RDS
SNS topic and subscription
ALB
Target Group
Web Launch Template
Scheduler Launch Template
Secrets Manager secret
EC2 IAM role
```

---

# 35. Final Checklist

## Local

- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Migration applied
- [ ] Seed data created
- [ ] Nine tests pass
- [ ] Product workflow works
- [ ] Order workflow works
- [ ] Low-stock notifier works

## Manual EC2

- [ ] Application cloned
- [ ] SQLite migration applied
- [ ] Browser access works
- [ ] Full workflow works
- [ ] Data survives process restart

## systemd

- [ ] Dedicated `inventory` user
- [ ] Code under `/opt`
- [ ] Configuration under `/etc`
- [ ] Data under `/var/lib`
- [ ] Web service enabled
- [ ] Timer enabled
- [ ] Web restarts after crash
- [ ] Services survive reboot
- [ ] SQLite parent-directory bug fixed

## RDS

- [ ] Private PostgreSQL RDS
- [ ] `kaizen_inventory` database
- [ ] `inventory_app` user
- [ ] Schema permissions
- [ ] Alembic migration applied
- [ ] Seed products created

## SNS

- [ ] SNS topic created
- [ ] Email subscription confirmed
- [ ] Scheduler role can publish
- [ ] Low-stock email received

## Web tier

- [ ] Web Launch Template
- [ ] Target Group
- [ ] ALB
- [ ] Web ASG
- [ ] Two healthy targets
- [ ] `/instance` shows multiple hosts
- [ ] Direct port 8000 access removed
- [ ] Replacement test succeeds

## Scheduler

- [ ] Dedicated scheduler Launch Template
- [ ] One scheduler instance
- [ ] Web service disabled on scheduler
- [ ] Timer active
- [ ] Timer survives reboot
- [ ] Scheduler reaches RDS
- [ ] Scheduler publishes to SNS

---

# 36. Troubleshooting

## Gunicorn exits with status 3

Check:

```bash
sudo journalctl \
  -u kaizen-inventory-web \
  -n 150 \
  --no-pager
```

Common causes:

- Environment file unreadable
- Database directory not writable
- Incorrect SQLite path handling
- PostgreSQL connection failure
- Missing dependency
- Invalid Secrets Manager value

## systemd service remains activating

The service is likely repeatedly restarting.

Check:

```bash
sudo systemctl status \
  kaizen-inventory-web \
  --no-pager

sudo journalctl \
  -u kaizen-inventory-web \
  -n 150 \
  --no-pager
```

Stop the restart loop while troubleshooting:

```bash
sudo systemctl stop \
  kaizen-inventory-web
```

## Low-stock oneshot fails

Check:

```bash
sudo systemctl status \
  kaizen-inventory-low-stock.service \
  --no-pager

sudo journalctl \
  -u kaizen-inventory-low-stock.service \
  -n 150 \
  --no-pager
```

## Local curl works but browser does not

Check:

```bash
sudo ss -lntp | grep 8000
```

Expected:

```text
0.0.0.0:8000
```

Verify temporary security-group access:

```text
TCP 8000 → Your current public IP/32
```

## RDS connection fails

Verify:

- Correct endpoint
- Port 5432
- RDS security group source
- Database name
- Username and password
- Private DNS resolution
- EC2 and RDS are in connected VPC networks

Test:

```bash
psql \
  -h RDS_ENDPOINT \
  -U inventory_app \
  -d kaizen_inventory \
  -W
```

## Database does not exist

Connect to:

```text
postgres
```

Then:

```sql
CREATE DATABASE kaizen_inventory;
```

## Cannot assign database ownership

Do not require:

```sql
CREATE DATABASE kaizen_inventory OWNER inventory_app;
```

Use:

```sql
CREATE DATABASE kaizen_inventory;
\c kaizen_inventory
GRANT CONNECT ON DATABASE kaizen_inventory TO inventory_app;
GRANT USAGE, CREATE ON SCHEMA public TO inventory_app;
```

## SNS notification does not arrive

Check:

- Subscription is confirmed
- `ALERT_BACKEND=sns`
- Correct topic ARN
- EC2 role includes `sns:Publish`
- Scheduler has role attached
- Product quantity is at or below reorder level
- Cooldown did not skip the alert

Check logs:

```bash
sudo journalctl \
  -u kaizen-inventory-low-stock.service \
  -n 100 \
  --no-pager
```

## Timer is active but notification has not run

Check:

```bash
systemctl list-timers \
  kaizen-inventory-low-stock.timer
```

Run immediately:

```bash
sudo systemctl start \
  kaizen-inventory-low-stock.service
```

## ALB returns 503

Check:

- Two targets are healthy
- Target port is 8000
- Health path is `/health`
- App SG allows 8000 from ALB SG
- Web service is active
- cloud-init completed
- RDS is reachable
- Migration was applied

## cloud-init failed

```bash
sudo cloud-init status --long

sudo tail -n 200 \
  /var/log/cloud-init-output.log

sudo tail -n 200 \
  /var/log/kaizen-inventory-bootstrap.log
```

## Secret cannot be read

Verify IAM:

```bash
aws sts get-caller-identity
```

Test only the ARN without printing secret contents:

```bash
aws secretsmanager get-secret-value \
  --secret-id kaizen-inventory/production \
  --region us-east-1 \
  --query ARN \
  --output text
```

---

# 37. Useful Commands

## Configuration

```bash
cd /opt/kaizen-inventory-hub

sudo -u inventory \
  /opt/kaizen-inventory-hub/.venv/bin/python \
  -c 'from app.config import get_settings; s = get_settings(); print(s.app_name, s.app_env, s.database_url, s.alert_backend)'
```

## Web service

```bash
sudo systemctl status \
  kaizen-inventory-web \
  --no-pager

sudo journalctl \
  -u kaizen-inventory-web \
  -n 100 \
  --no-pager
```

## Timer

```bash
systemctl list-timers \
  kaizen-inventory-low-stock.timer
```

## Manual notification

```bash
sudo systemctl start \
  kaizen-inventory-low-stock.service
```

## Target health

```bash
aws elbv2 describe-target-health \
  --target-group-arn TARGET_GROUP_ARN
```

## ASG activity

```bash
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name kaizen-inventory-web-asg \
  --max-items 10
```

---

# 38. Optional Future Improvements

Not required for the current lab:

- CPU target-tracking scaling policy
- CloudWatch alarms
- SNS infrastructure alarms
- Centralized application logs
- CloudWatch Agent
- HTTPS with ACM
- Route 53
- AWS WAF
- Private web subnets
- NAT Gateway
- VPC endpoints
- Systems Manager Session Manager
- Scheduler Auto Scaling Group with desired capacity 1
- EventBridge Scheduler
- SQS job queue
- RDS Multi-AZ
- Read replicas
- CI/CD pipeline
- Docker image deployment
- Amazon ECS
- Terraform
- Blue/green deployment
- Database migration pipeline
- Application authentication and authorization

---

# 39. Suggested Instructor Demonstration Order

1. Explain inventory and order features.
2. Run locally with SQLite.
3. Apply the migration.
4. Seed sample products.
5. Run nine tests.
6. Create and adjust products.
7. Create an order and observe stock deduction.
8. Run the console low-stock notifier.
9. Deploy manually to EC2.
10. Repeat the functional workflow.
11. Introduce Linux application layout.
12. Create the service user.
13. Move code, configuration, and data.
14. Create the Gunicorn systemd service.
15. Create the low-stock timer.
16. Demonstrate the SQLite directory-permission bug.
17. Apply the corrected database-path logic.
18. Test crash restart and reboot persistence.
19. Explain why SQLite cannot support the final multi-instance architecture.
20. Build the custom VPC.
21. Create private PostgreSQL RDS.
22. Create the application DB user.
23. Create SNS and confirm subscription.
24. Create the IAM role.
25. Create the production secret.
26. Add web and scheduler bootstrap scripts.
27. Validate one web template instance.
28. Run migration once.
29. Create the Target Group and ALB.
30. Create the web ASG.
31. Validate two healthy web instances.
32. Launch the dedicated scheduler instance.
33. Test SNS delivery.
34. Remove direct port 8000 access.
35. Terminate one web instance.
36. Observe automatic ASG replacement.
37. Verify data remains in RDS.

---

# 40. Completion Criteria

The project is complete when:

1. The application works locally.
2. Nine tests pass.
3. Product and inventory workflows work.
4. Orders reduce stock transactionally.
5. Negative stock is prevented.
6. Low-stock reporting works.
7. The application works on one EC2 instance.
8. systemd manages the web process.
9. systemd schedules low-stock checks.
10. The SQLite production-path issue is corrected.
11. PostgreSQL RDS is private.
12. Alembic migrations succeed against PostgreSQL.
13. Products and orders persist across instances.
14. SNS sends low-stock email notifications.
15. EC2 uses an IAM role.
16. Production settings come from Secrets Manager.
17. The ALB routes to two healthy web instances.
18. `/instance` demonstrates load distribution.
19. Only the dedicated scheduler runs the timer.
20. Terminating one web instance does not lose application data.
21. ASG restores the desired web capacity.
