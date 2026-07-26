from app.alerts import send_low_stock_alerts
from app.database import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        sent, skipped = send_low_stock_alerts(db)
        print(f"Low-stock notification run complete: sent={sent} skipped={skipped}")


if __name__ == "__main__":
    main()
