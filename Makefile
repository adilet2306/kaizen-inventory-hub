.PHONY: install migrate seed run test notify docker-up docker-down

install:
	python -m pip install -r requirements.txt

migrate:
	python -m alembic upgrade head

seed:
	python -m app.seed

run:
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	python -m pytest -q

notify:
	python -m app.notify_low_stock

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
