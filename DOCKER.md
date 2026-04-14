# Docker Setup for Navigation Service

This project uses a lean Docker Compose architecture:
- one runtime service (`api`)
- one local override for development (`docker-compose.override.yml`)
- one CI compose file (`docker-compose.ci.yml`)
- external Neon PostgreSQL (no local DB container)

## Prerequisites

- Docker and Docker Compose
- Neon PostgreSQL connection string

## Quick Start

```bash
# 1) Create .env
cp .env.example .env

# 2) Set required variables
# DATABASE_URL=postgresql+asyncpg://user:password@host.neon.tech/dbname?ssl=require
# TEST_DATABASE_URL=postgresql+asyncpg://user:password@host.neon.tech/dbname_test?ssl=require

# 3) Start local development (base + override)
docker compose up -d api

# 4) Verify service
curl http://localhost:8000/health
```

## Compose Modes

### Local development (default command path)

`docker compose` automatically merges:
- `docker-compose.yml`
- `docker-compose.override.yml`

So the `api` service runs in development mode with hot reload.

```bash
docker compose up -d api
docker compose logs -f api
```

### Production-style run (base only)

Use only `docker-compose.yml` to avoid development overrides:

```bash
docker compose -f docker-compose.yml up -d api
docker compose -f docker-compose.yml logs -f api
```

### CI jobs

Use the dedicated CI compose file:

```bash
docker compose -f docker-compose.ci.yml run --rm test-runner
docker compose -f docker-compose.ci.yml run --rm lint
```

## Service Model

- `api`: FastAPI service (port `8000`)
- `test-runner`: CI-only pytest service in `docker-compose.ci.yml`
- `lint`: CI-only lint service in `docker-compose.ci.yml`

No `db`, `redis`, `pgadmin`, or monitoring services are part of this setup.

## Makefile Shortcuts

```bash
make dev       # local dev (with override)
make up-prod   # production-style run (base only)
make test      # CI test-runner job
make ci-lint   # CI lint job
make logs      # tail api logs
make down      # stop containers
```

## Environment Variables

Required:
- `DATABASE_URL`

Recommended:
- `TEST_DATABASE_URL`
- `API_PORT`
- `LOG_LEVEL`
- `CORS_ORIGINS`
- `ALLOWED_HOSTS`

## Troubleshooting

```bash
# Inspect fully rendered local config
docker compose config

# Inspect CI config
docker compose -f docker-compose.ci.yml config

# Check service logs
docker compose logs -f api
```
