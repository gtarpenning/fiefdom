.PHONY: dev-install run migrate seed test-e2e lint

dev-install:
	python -m pip install -e '.[dev]'

run:
	CUPBEARER_ENV=dev uvicorn cupbearer.main:app --host 0.0.0.0 --port 8000

migrate:
	python scripts/migrate.py

seed:
	python scripts/seed.py

test-e2e:
	python -m pytest -m e2e tests/e2e

lint:
	ruff check src tests
