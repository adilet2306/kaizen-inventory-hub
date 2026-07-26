from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "Kaizen Inventory Hub"
    app_env: str = "development"
    app_version: str = "1.0.0"
    secret_key: str = "change-me"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    database_url: str = "sqlite:///./instance/inventory.db"

    alert_backend: str = "console"
    sns_topic_arn: str = ""
    aws_region: str = "us-east-1"
    low_stock_cooldown_minutes: int = 60

    metrics_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
