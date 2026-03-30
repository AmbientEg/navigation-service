# CLAUDE.md

This file provides project-specific guidance for working in this repository.

## Project Overview

Indoor Navigation API built with FastAPI, SQLAlchemy async ORM, PostGIS/GeoAlchemy2, and NetworkX.

Core domain intent:
- Store indoor floor maps as GeoJSON in the database.
- Build navigation graph data from GeoJSON (derived data).
- Version graph snapshots per building.
- Route users using only the active graph version.

## Tech Stack

- FastAPI
- SQLAlchemy 2.x async + asyncpg
- PostgreSQL + PostGIS + GeoAlchemy2
- NetworkX
- Uvicorn
- Pydantic
- python-dotenv

## Runtime And Setup

The repository uses a local virtual environment at `nav-service/`.

Activate:
```bash
source nav-service/bin/activate
```

Install dependencies (if needed):
```bash
./nav-service/bin/pip install uvicorn fastapi sqlalchemy asyncpg psycopg2-binary pydantic geoalchemy2 networkx python-dotenv greenlet
```

Run app:
```bash
./nav-service/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Fallback if port 8000 is occupied:
```bash
./nav-service/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010
```

Test DB connection helper:
```bash
./nav-service/bin/python database.py
```

## Environment Variables

```bash
DATABASE_URL=postgresql://...        # Required
ENVIRONMENT=development|production   # Optional
LOG_LEVEL=INFO|DEBUG|WARNING         # Optional
CORS_ORIGINS=*                       # Optional, comma-separated
ALLOWED_HOSTS=*                      # Optional, comma-separated
AWS_LAMBDA_FUNCTION_NAME=            # Optional, if running in Lambda
```

Notes:
- `database.py` auto-converts `postgresql://` to `postgresql+asyncpg://`.
- It strips unsupported asyncpg URL query params (`sslmode`, `channel_binding`, `gssencmode`).

## High-Level Architecture

Data separation:
- Source of truth: `floors.floor_geojson` (raw GeoJSON FeatureCollection).
- Derived graph: `routing_nodes` + `routing_edges` (version-scoped).
- Graph versioning: `navigation_graph_versions` with `is_active` per building.

Graph lifecycle:
1. Rebuild preview in memory from all floors of a building.
2. Confirm persists nodes/edges as a new graph version and activates it.
3. Rollback switches active version to previous one.

Routing lifecycle:
1. Validate source floor and destination POI.
2. Ensure same building.
3. Load active graph version.
4. Resolve nearest start/end nodes within that version.
5. Build versioned graph and compute shortest path.

## Main App Surface

File: `main.py`

Includes:
- Lifespan startup/shutdown with DB initialization.
- Security headers middleware.
- Request logging + correlation IDs.
- HTTP and global exception handlers.
- Health probes (`/health`, `/health/ready`, `/health/live`).
- Operational metadata endpoints (`/`, `/api/status`, `/api/feedback`).

Routers mounted:
- `/api/buildings`
- `/api/floors`
- `/api/navigation`
- `/api/graphs`

## API Endpoints

Buildings (`routes/buildings_routes.py`):
- `POST /api/buildings`
- `GET /api/buildings/{building_id}`
- `GET /api/buildings/{building_id}/floors`

Floors (`routes/floors_routes.py`):
- `POST /api/floors`
- `PUT /api/floors/{floor_id}`
- `GET /api/floors/{floor_id}/map`

Graphs (`routes/graph_routes.py`):
- `POST /api/graphs/rebuild/{building_id}`
- `POST /api/graphs/confirm/{building_id}`
- `POST /api/graphs/rollback/{building_id}`

Navigation (`routes/navigation_routes.py`):
- `POST /api/navigation/route`

## Core Data Models

Key model files:
- `models/buildings.py`
- `models/floors.py`
- `models/poi.py`
- `models/node_types.py`
- `models/edge_types.py`
- `models/routing_nodes.py`
- `models/routing_edges.py`
- `models/navigation_graph_versions.py`

Model design conventions:
- UUID primary keys across entities.
- Spatial columns use GeoAlchemy2 geometry types.
- Graph nodes/edges include `graph_version_id` to bind them to one version.

## Graph Pipeline Details

File: `pipeline/step2_construct_graph.py`

Important functions:
- `build_navigation_graph(geojson: dict) -> nx.Graph`
- `load_geojson_from_dict(geojson: dict)`
- `graph_to_geojson_dict(G)`

Pipeline behavior:
- Classifies GeoJSON features (corridors, doors, rooms).
- Builds corridor backbone and junctions.
- Attaches doors and rooms.
- Removes self-loop and zero-length edges.

## Graph Workflow Service

File: `services/graph_workflow_service.py`

Important methods:
- `build_graph_preview_for_building(db, building_id)`
- `confirm_graph_preview(db, building_id, preview)`
- `rollback_to_previous_graph_version(db, building_id)`
- `get_active_graph_version(db, building_id)`

Stitching behavior:
- Always stitches adjacent floors.
- Prefers vertical-node name matching (stairs/elevator/lift/etc.).
- Falls back to nearest-node pair if no named vertical match exists.

## Routing Service

File: `services/routing_service.py`

Important behavior:
- `find_nearest_node(...)` is constrained by `graph_version_id`.
- `build_graph_for_floors(...)` loads nodes/edges only for one graph version.
- `calculate_route(...)` blocks cross-building routes and requires active version.

## Database And Migrations

Database manager file:
- `database.py`

Alembic migration setup:
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/001_initial_schema.py`
- `alembic/versions/6845ad39a047_baseline_schema_20260330.py`
- `alembic/versions/7c24d182ba01_graph_versioning_managed.py`

Important operational note:
- `Base.metadata.create_all()` creates missing tables but does not perform full schema migrations for existing tables.
- Use Alembic for all schema changes (`alembic revision`, `alembic upgrade head`).

Required DB extension:
```sql
CREATE EXTENSION postgis;
```

## Documentation And Postman Assets

Primary docs:
- `API_DOCUMENTATION.md`
- `ARCHITECTURE_WORKFLOW.md`
- `README.md`

Postman files:
- `postman/Indoor-Navigation-API.postman_collection.json`
- `postman/Indoor-Navigation-Local.postman_environment.json`

## Working Conventions

- Keep floor GeoJSON as authoritative input; do not manually mutate derived graph data.
- Use rebuild/confirm workflow after map updates.
- Keep one active graph version per building.
- Use async SQLAlchemy sessions via `Depends(get_db_session)`.
- Keep spatial queries in DB (`ST_Distance`, `ST_AsText`) when selecting/locating nodes.
