.PHONY: up down logs seed test fmt

up:
	cd deploy && docker compose up -d --build

down:
	cd deploy && docker compose down

logs:
	cd deploy && docker compose logs -f api

seed:
	cd deploy && docker compose exec api python -m app.db.seed

fmt:
	ruff format app || true
