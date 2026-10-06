SHELL := /bin/sh
EVAL_SOURCES := ../eval/__init__.py ../eval/evaluate.py ../eval/matching.py ../eval/metrics.py ../eval/report.py

.PHONY: up down eval lint test fmt check-python

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

lint: check-python
	cd api && test -z "$$(gofmt -l .)"
	cd api && go vet ./...
	cd api && golangci-lint run
	cd worker && python -m ruff format --check app vision tests $(EVAL_SOURCES) ../eval/tests
	cd worker && python -m ruff check app vision tests $(EVAL_SOURCES) ../eval/tests
	cd worker && python -m mypy --strict app vision $(EVAL_SOURCES)
	cd web && npm run lint

test: check-python
	cd api && go test ./...
	cd worker && python -m pytest tests ../eval/tests

fmt:
	cd api && gofmt -w .
	cd worker && python -m ruff format app vision tests $(EVAL_SOURCES) ../eval/tests
	cd web && npm run fmt
