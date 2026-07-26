import os
from pathlib import Path

import pytest

TEST_DB = Path("instance/test_inventory.db").resolve()
TEST_DB.parent.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["APP_ENV"] = "test"
os.environ["ALERT_BACKEND"] = "console"
os.environ["LOW_STOCK_COOLDOWN_MINUTES"] = "60"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
