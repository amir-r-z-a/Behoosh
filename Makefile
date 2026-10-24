.PHONY: up down logs migrate seed test lint fmt

up:
	cd deploy && docker compose up -d --build

down:
	cd deploy && docker compose down

logs:
	cd deploy && docker compose logs -f api

migrate:
	cd deploy && docker compose exec api python -m app.db.migrate

seed:
	cd deploy && docker compose exec api python -m app.db.seed

# نیاز به یک Postgres خالی: TEST_DATABASE_URL=postgresql+psycopg://user@host:port/db
test:
	pytest

lint:
	ruff check app tests

fmt:
	ruff format app tests
