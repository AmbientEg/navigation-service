# Navigation Service Deployment Guide

This deployment flow is aligned with the lean Compose architecture:
- `docker-compose.yml`: base runtime (`api`)
- `docker-compose.override.yml`: local development overrides
- `docker-compose.ci.yml`: CI jobs (`test-runner`, `lint`)

The service uses an external Neon PostgreSQL database.

## Files

- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.override.yml`
- `docker-compose.ci.yml`
- `docker-entrypoint.sh`
- `.dockerignore`
- `.env.example`
- `Makefile`

## Quick Start

```bash
# 1) Prepare environment
cp .env.example .env

# 2) Configure required variables in .env
# DATABASE_URL=postgresql+asyncpg://user:password@host.neon.tech/db?ssl=require
# TEST_DATABASE_URL=postgresql+asyncpg://user:password@host.neon.tech/db_test?ssl=require

# 3) Start local development mode (base + override)
make dev

# 4) Check health
make health
```

## Runtime Modes

### Local development

```bash
make dev
make logs
```

Uses default Compose layering (`docker-compose.yml` + `docker-compose.override.yml`) so `api` runs with development settings and hot reload.

### Production-style run

```bash
make up-prod
```

Uses base file only (`docker-compose.yml`) to avoid local development overrides.

## CI Execution

```bash
make test
make ci-lint
```

Equivalent raw commands:

```bash
docker compose -f docker-compose.ci.yml run --rm test-runner
docker compose -f docker-compose.ci.yml run --rm lint
```

## Deploy Checklist

1. Set `DATABASE_URL` to production Neon connection.
2. Set `ENVIRONMENT=production` and appropriate `ALLOWED_HOSTS`.
3. Build production image: `make build-prod`.
4. Start production-style service: `make up-prod`.
5. Verify: `curl http://localhost:8000/health`.

## Troubleshooting

```bash
# Render local merged configuration
docker compose config

# Render CI configuration
docker compose -f docker-compose.ci.yml config

# Tail runtime logs
docker compose logs -f api
```
