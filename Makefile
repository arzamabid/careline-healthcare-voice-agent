.PHONY: \
	run \
	test \
	lint \
	check \
	db-up \
	db-down \
	db-migrate \
	db-seed \
	eval-core \
	eval-stt \
	eval-latency \
	eval

run:
	uvicorn apps.api.main:app --reload

test:
	pytest -v

lint:
	ruff check .

check: lint test

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-migrate:
	alembic upgrade head

db-seed:
	python scripts/seed_db.py

eval-core:
	python -m evaluations.run_all_evals

eval-stt:
	python -m evaluations.run_stt_evals

eval-latency:
	python -m evaluations.run_latency_evals

eval: eval-core eval-stt eval-latency