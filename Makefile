# FairDataHive — common local commands (run from repo root)

.PHONY: help up down logs dev-api dev-ui test build-ui build-api check

help:
	@echo "Targets:"
	@echo "  make up        - docker compose up -d (production-like API image)"
	@echo "  make dev-api   - compose with hot-reload API (docker-compose.dev.yml)"
	@echo "  make dev-ui    - Vite dev server on http://localhost:5173"
	@echo "  make down      - docker compose down"
	@echo "  make test      - pytest (unit tests, in-memory DB)"
	@echo "  make build-ui  - npm run build in frontend/"
	@echo "  make build-api - build UI then docker compose build api"
	@echo "  make check     - test + build-ui (run before git push)"

up:
	docker compose up -d

dev-api:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

dev-ui:
	cd frontend && npm run dev

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	pytest tests/ -x -m "not integration" --tb=short

build-ui:
	cd frontend && npm ci && npm run build

build-api: build-ui
	docker compose build api

check: test build-ui
