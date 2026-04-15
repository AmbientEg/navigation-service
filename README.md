# Indoor Navigation Service

FastAPI backend for indoor map management, graph versioning, and shortest-path routing in multi-floor buildings.

## Project Overview

This service stores floor maps as GeoJSON, derives navigation graph data from those maps, versions graph snapshots per building, and computes routes using the currently active graph version only.

Core capabilities:

- Building and floor management
- Graph rebuild/preview/confirm/rollback workflow
- Versioned graph storage for safe map evolution
- Route calculation between source and destination points/POIs

## Tech Stack

- FastAPI
- SQLAlchemy 2.x async ORM
- asyncpg
- PostgreSQL + PostGIS + GeoAlchemy2
- NetworkX
- Pydantic
- Alembic
- Uvicorn

## Architecture Summary

High-level data flow:

1. Clients upload/update floor GeoJSON.
2. Pipeline/services construct a navigation graph from authoritative GeoJSON.
3. Graph preview is validated, then confirmed as a new graph version.
4. A single graph version is marked active per building.
5. Routing uses only active-version nodes/edges.

Key layers:

- API routes: request validation and HTTP surface
- Services: graph workflow and routing business logic
- Models: buildings/floors/POI/node/edge/version entities
- Database: Postgres/PostGIS for persistence and spatial queries

## Local Development Setup

Prerequisites:

- Python 3.12+
- PostgreSQL with PostGIS extension enabled
- Virtual environment at nav-service (or your own venv)

Install dependencies:

```bash
source nav-service/bin/activate
./nav-service/bin/pip install -r requirements.txt
```

Configure environment:

```bash
cp .env.example .env
# then edit .env
```

Enable PostGIS in your database:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

Run migrations:

```bash
source nav-service/bin/activate
alembic upgrade head
```

## How To Run The Service

Development run:

```bash
source nav-service/bin/activate
./nav-service/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Production-style local run (no reload):

```bash
source nav-service/bin/activate
./nav-service/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Startup Instructions

After startup, verify:

- API root: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/health
- Readiness: http://127.0.0.1:8000/health/ready
- Liveness: http://127.0.0.1:8000/health/live
- Swagger docs (non-production): http://127.0.0.1:8000/docs

## Docker Setup

Build image:

```bash
docker build -t navigation-api .
```

Run container (port 8000 + env injection):

```bash
docker run -p 8000:8000 --env-file .env navigation-api
```

Production image uses:

- Multi-stage build
- Non-root runtime user
- Uvicorn without --reload

## Docker Compose Status

No docker-compose.yml is currently present in this repository.

If you add Compose later, define at minimum:

- api service (this app)
- db service (postgres/postgis)
- shared network and persistent db volume

Example commands after adding compose file:

```bash
docker compose up --build
docker compose down
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| DATABASE_URL | Yes | - | Main database connection URL. |
| ENVIRONMENT | No | development | Controls production behavior (docs visibility, logging defaults). |
| LOG_LEVEL | No | INFO | Application log level. |
| SQLALCHEMY_ECHO | No | true in development, false in production | Enables SQL echo logging from SQLAlchemy. |
| CORS_ORIGINS | No | * | Comma-separated allowed CORS origins. |
| ALLOWED_HOSTS | No | * | Comma-separated trusted hosts for production middleware. |
| AWS_LAMBDA_FUNCTION_NAME | No | empty | Indicates Lambda runtime mode when set. |
| ADMIN_API_TOKEN | No* | empty | Bearer token for admin-protected endpoints. Required if admin endpoints are enabled/used. |
| TEST_DATABASE_URL | No | empty | Test database connection string for integration tests. |
| APP_PORT | No | 8000 | Optional app port variable for deployment scripts. |
| NGINX_PORT | No | 80 | Optional reverse proxy port. |
| NGINX_SSL_PORT | No | 443 | Optional reverse proxy TLS port. |
| APP_UID | No | 1000 | Optional container UID mapping. |
| APP_GID | No | 1000 | Optional container GID mapping. |
| AWS_REGION | No | us-east-1 | Optional AWS region value for Lambda/integration scripts. |

URL notes:

- Runtime supports postgresql:// and postgresql+asyncpg:// formats.
- Unsupported asyncpg query parameters (sslmode, channel_binding, gssencmode) are stripped automatically.

## API Endpoints

- Buildings
- POST /api/buildings
- GET /api/buildings/{building_id}
- GET /api/buildings/{building_id}/floors
- Floors
- POST /api/floors
- PUT /api/floors/{floor_id}
- GET /api/floors/{floor_id}/map
- Graphs
- POST /api/graphs/rebuild/{building_id}
- POST /api/graphs/confirm/{building_id}
- POST /api/graphs/rollback/{building_id}
- Navigation
- POST /api/navigation/route

## Testing

```bash
source nav-service/bin/activate
python -m pytest tests/unit/ -q
python -m pytest tests/integration/ -q
python -m pytest tests/ -v
```

## Troubleshooting

Database connection fails:

- Confirm DATABASE_URL is set and reachable.
- Confirm PostGIS extension is installed.
- Verify network/firewall/SSL settings for managed DB providers.

Health endpoint reports degraded:

- Check DB connectivity and credentials.
- Verify migrations are applied.

Container exits at startup:

- Ensure .env contains required DATABASE_URL.
- Check logs: docker logs <container_id>.

Swagger docs missing:

- Docs are disabled when ENVIRONMENT=production.

Alembic migration errors:

- Ensure DATABASE_URL is present in shell/.env before running alembic commands.

Admin endpoints return 503/401:

- Set ADMIN_API_TOKEN in .env and send Authorization: Bearer <token>.

