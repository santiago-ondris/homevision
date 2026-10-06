SHELL := /bin/sh
EVAL_SOURCES := ../eval/__init__.py ../eval/evaluate.py ../eval/matching.py ../eval/metrics.py ../eval/report.py

.PHONY: up down eval lint lint-api lint-worker lint-web test test-api test-worker fmt check-python

up:
	docker compose up --build

down:
	docker compose down

eval:
	docker compose run --rm eval

check-python:
	@case "$$(python --version 2>&1)" in \
		"Python 3.14."*) ;; \
		*) echo "Python 3.14 is required; activate the virtual environment described in the README"; exit 1 ;; \
	esac

lint: lint-api lint-worker lint-web

lint-api:
	cd api && test -z "$$(gofmt -l .)"
	cd api && go vet ./...
	cd api && golangci-lint run

lint-worker: check-python
	cd worker && python -m ruff format --check app vision tests $(EVAL_SOURCES) ../eval/tests
	cd worker && python -m ruff check app vision tests $(EVAL_SOURCES) ../eval/tests
	cd worker && python -m mypy --strict app vision $(EVAL_SOURCES)

lint-web:
	cd web && npm run lint

test: test-api test-worker

test-api:
	cd api && go test ./...

test-worker: check-python
	cd worker && python -m pytest tests ../eval/tests

fmt:
	cd api && gofmt -w .
	cd worker && python -m ruff format app vision tests $(EVAL_SOURCES) ../eval/tests
	cd web && npm run fmt
