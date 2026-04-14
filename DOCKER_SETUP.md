# Docker Setup for Navigation Service

This guide explains how to run the Navigation Service using a single Compose service (`api`) with an external Neon PostgreSQL database.

## Prerequisites

- Docker and Docker Compose installed
- Neon PostgreSQL database account (sign up at https://neon.tech)

## Quick Start

```bash
# 1. Clone/copy .env.example to .env and customize
cp .env.example .env

# 2. Add your Neon database connection string to .env
# DATABASE_URL=postgresql+asyncpg://user:password@your-project.neon.tech/navigation?ssl=require

# 3. Start production API
docker compose up -d

# 4. Verify it's working
curl http://localhost:8000/health
```

## Services Overview

| Service | Port | Description | Profile |
|---------|------|-------------|---------|
| API | 8000 | FastAPI service (dev via override, prod via base file) | default |
| Test Runner | - | CI test runner (`docker-compose.ci.yml`) | CI file |
| Lint | - | CI lint runner (`docker-compose.ci.yml`) | CI file |

**Note**: No local PostgreSQL, Redis, pgAdmin, or monitoring containers.

## Commands

### Development Mode
```bash
# Start with hot reload
docker compose up -d api

# View logs
docker compose logs -f api

# Stop
docker compose down
```

### Production Mode
```bash
# Start production services
docker compose -f docker-compose.yml up -d api

# View logs
docker compose -f docker-compose.yml logs -f api

# Stop
docker compose -f docker-compose.yml down
```

### Running Tests
```bash
# Run tests against external database
docker compose -f docker-compose.ci.yml run --rm test-runner

# Run lint checks
docker compose -f docker-compose.ci.yml run --rm lint
```

## Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
# Required: Neon database connection string
DATABASE_URL=postgresql+asyncpg://user:password@your-project.neon.tech/navigation?ssl=require

# Optional: Separate test database
TEST_DATABASE_URL=postgresql+asyncpg://user:password@your-project.neon.tech/navigation_test?ssl=require

# Application settings
ENVIRONMENT=development
LOG_LEVEL=INFO
API_PORT=8000
CORS_ORIGINS=http://localhost:3000
ALLOWED_HOSTS=localhost,api.example.com
```

### Getting Your Neon Connection String

1. Sign up at https://neon.tech
2. Create a new project
3. Go to the project dashboard
4. Click "Connection Details"
5. Copy the connection string
6. Replace `postgresql://` with `postgresql+asyncpg://`

## Dynamic Image Configuration

The Dockerfile supports multiple build targets via `--target`:

- `base`: Common dependencies
- `development`: Development with hot reload
- `production`: Optimized production image
- `test`: Test runner

### Build Custom Images
```bash
# Build specific target
docker build --target production -t myapp:prod .

# With custom build args
docker build \
  --target production \
  --build-arg APP_USER=myuser \
  --build-arg APP_UID=1001 \
  -t myapp:custom .
```

## Multi-Stage Build Benefits

1. **Smaller Images**: Production image doesn't include dev tools
2. **Faster Builds**: Caches dependency layer separately
3. **Security**: Runs as non-root user
4. **Flexibility**: Same Dockerfile for all environments

## Docker Compose Profiles

This setup relies on Compose file layering, not profiles:

- Local development: `docker compose ...` (base + override)
- Production-style run: `docker compose -f docker-compose.yml ...` (base only)
- CI jobs: `docker compose -f docker-compose.ci.yml ...`

## Troubleshooting

### Port Conflicts
If ports are already in use, modify in `.env`:
```bash
API_PORT=8001
NGINX_PORT=8080
```

### Database Connection Issues
```bash
# Verify DATABASE_URL is set correctly
echo $DATABASE_URL

# Test connection from local environment
source nav-service/bin/activate
python database.py

# Test from within container
docker compose exec api sh -c "python -c 'from database import test_connection; import asyncio; asyncio.run(test_connection())'"
```

### Hot Reload Not Working
Ensure you're using default Compose layering (without `-f docker-compose.yml`):
```bash
docker compose up -d api
```

# Clean Slate
```bash
# Remove everything
docker compose down

# Full system cleanup
docker system prune -af
```

## Production Deployment

1. **Set production variables**:
```bash
ENVIRONMENT=production
ALLOWED_HOSTS=api.example.com
CORS_ORIGINS=https://app.example.com
DATABASE_URL=postgresql+asyncpg://...neon.tech...
```

2. **Use production profile**:
```bash
docker compose -f docker-compose.yml up -d api
```

3. **Scale API instances** (requires load balancer configuration):
```bash
docker compose up -d --scale api=3
```

## Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check all containers
docker compose ps
```

## CI/CD with External Database

For CI pipelines, use separate Neon database branches:

```yaml
# GitHub Actions example
- name: Run tests
  env:
    TEST_DATABASE_URL: ${{ secrets.NEON_TEST_DATABASE_URL }}
  run: docker compose -f docker-compose.ci.yml run --rm test-runner
```
