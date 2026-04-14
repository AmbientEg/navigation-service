# Navigation Service - Lean Docker Makefile
# Single-service Compose workflow with external Neon PostgreSQL.

.PHONY: help env build build-prod build-dev dev up-prod down logs restart status shell test ci-test ci-lint clean clean-images prune health dc

help:
	@echo "Navigation Service Docker Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make env       - Create .env from .env.example"
	@echo "  make build     - Build local dev image (compose with override)"
	@echo "  make build-dev - Build development target image"
	@echo "  make build-prod - Build production target image"
	@echo ""
	@echo "Run:"
	@echo "  make dev       - Start local development (override file active)"
	@echo "  make up-prod   - Start production-style stack (base compose only)"
	@echo "  make down      - Stop containers"
	@echo "  make logs      - Follow api logs"
	@echo "  make restart   - Restart api service"
	@echo "  make status    - Show compose status"
	@echo "  make shell     - Open shell in api container"
	@echo ""
	@echo "CI:"
	@echo "  make test      - Run CI test-runner service"
	@echo "  make ci-lint   - Run CI lint service"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Stop containers and remove local caches"
	@echo "  make clean-images - Remove local navigation-service images"
	@echo "  make prune        - Docker system prune"
	@echo "  make health       - Check health endpoint"

# =============================================================================
# Environment Setup
# =============================================================================

env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env file created from .env.example"; \
		echo "Please edit .env with your configuration"; \
	else \
		echo ".env file already exists"; \
	fi

# =============================================================================
# Building
# =============================================================================

build: env
	docker compose build --parallel api

build-prod:
	docker compose -f docker-compose.yml build --parallel api

build-dev:
	docker compose build --parallel api

dev: env
	docker compose up -d api
	@echo "Development server started at http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"

up-prod: env
	docker compose -f docker-compose.yml up -d api
	@echo "Production-style api started at http://localhost:8000"

down:
	docker compose down

logs:
	docker compose logs -f api

restart:
	docker compose restart api

status:
	docker compose ps

test:
	docker compose -f docker-compose.ci.yml run --rm test-runner

ci-test:
	docker compose -f docker-compose.ci.yml run --rm test-runner

ci-lint:
	docker compose -f docker-compose.ci.yml run --rm lint

clean:
	docker compose down --remove-orphans
	rm -rf __pycache__ .pytest_cache htmlcov

clean-images:
	docker compose down
	docker rmi navigation-service:dev navigation-service:prod 2>/dev/null || true

prune:
	docker system prune -f --volumes

shell:
	docker compose exec api /bin/bash

health:
	@curl -s http://localhost:8000/health | python -m json.tool || echo "Health check failed"

# Dynamic command for any docker compose operation
dc:
	docker compose $(filter-out $@,$(MAKECMDGOALS))

# Catch-all target
%:
	@:
