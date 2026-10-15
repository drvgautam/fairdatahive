# FairDataHive — common local commands (run from repo root)

.PHONY: help up down logs dev-api dev-ui test test-storage build-ui build-api check

help:
	@echo "Targets:"
	@echo "  make up        - docker compose up -d (production-like API image)"
	@echo "  make dev-api   - compose with hot-reload API (docker-compose.dev.yml)"
	@echo "  make dev-ui    - Vite dev server on http://localhost:5173"
	@echo "  make down      - docker compose down"
	@echo "  make test      - pytest (unit tests, in-memory DB)"
	@echo "  make test-storage - S3 compatibility tests against the pinned RustFS container"
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

# S3 compatibility suite against the pinned RustFS image from docker-compose.yml.
# Uses the compose root key (local only) and host port 9002.
test-storage:
	docker compose up -d rustfs
	@echo "Waiting for RustFS on :9002..."
	@i=0; until curl -sf http://127.0.0.1:9002/health >/dev/null; do \
		i=$$((i+1)); \
		if [ $$i -ge 30 ]; then echo "RustFS did not become healthy" >&2; exit 1; fi; \
		sleep 1; \
	done
	STORAGE_INTEGRATION_ENDPOINT=http://127.0.0.1:9002 \
	STORAGE_INTEGRATION_ACCESS_KEY=$${RUSTFS_ROOT_ACCESS_KEY:-rustfsadmin} \
	STORAGE_INTEGRATION_SECRET_KEY=$${RUSTFS_ROOT_SECRET_KEY:-rustfsadmin} \
	pytest tests/test_storage_integration.py -m integration -v --tb=short

build-ui:
	cd frontend && npm ci && npm run build

build-api: build-ui
	docker compose build api

check: test build-ui
