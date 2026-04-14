
# Indoor Navigation Service

FastAPI backend for indoor map storage, graph versioning, and route calculation.

This service treats floor GeoJSON as source-of-truth and derives routing graphs
from it. Routing always runs against the active graph version for the building.

## Tech Stack

- FastAPI
- SQLAlchemy 2.x async + asyncpg
- PostgreSQL + PostGIS + GeoAlchemy2
- NetworkX
- Pydantic

## Project Layout

```text
.
├─ main.py
├─ database.py
├─ models/
├─ routes/
│  ├─ buildings_routes.py
│  ├─ floors_routes.py
│  ├─ graph_routes.py
│  └─ navigation_routes.py
├─ services/
│  ├─ graph_workflow_service.py
│  └─ routing_service.py
├─ pipeline/
│  ├─ run_graph_pipeline.py
│  └─ step2_construct_graph.py
├─ tests/
│  ├─ unit/
│  └─ integration/
└─ nav-service/  # local virtual environment
```

## Setup

```bash
source nav-service/bin/activate
./nav-service/bin/pip install -r requirements.txt
```

If you need a minimal explicit install:

```bash
./nav-service/bin/pip install uvicorn fastapi sqlalchemy asyncpg psycopg2-binary pydantic geoalchemy2 networkx python-dotenv greenlet
```

## Environment Variables

```bash
DATABASE_URL=postgresql://...
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=*
ALLOWED_HOSTS=*
```

Notes:

- `DATABASE_URL` is required.
- `database.py` converts `postgresql://` to `postgresql+asyncpg://` and strips unsupported asyncpg query params.

## Run Service

```bash
./nav-service/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Fallback port:

```bash
./nav-service/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010
```

## Graph Versioning Workflow

1. Update/create floor GeoJSON.
2. Rebuild graph preview for a building.
3. Confirm preview to persist a new graph version and activate it.
4. Roll back to previous version if needed.

Routing endpoints use only the active graph version.

## API Surface

- Buildings:
    - `POST /api/buildings`
    - `GET /api/buildings/{building_id}`
    - `GET /api/buildings/{building_id}/floors`
- Floors:
    - `POST /api/floors`
    - `PUT /api/floors/{floor_id}`
    - `GET /api/floors/{floor_id}/map`
- Graphs:
    - `POST /api/graphs/rebuild/{building_id}`
    - `POST /api/graphs/confirm/{building_id}`
    - `POST /api/graphs/rollback/{building_id}`
- Navigation:
    - `POST /api/navigation/route`

## Database Notes

Enable PostGIS in your target database:

```sql
CREATE EXTENSION postgis;
```

Use Alembic for schema evolution. `create_all()` is not a replacement for full migrations on existing tables.

## Test Coverage

### Unit Tests

#### Pipeline Tests (test_pipeline.py)

- GeoJSON loading and validation (empty, invalid, non-FeatureCollection)
- Feature classification (corridors, doors, rooms, stairs)
- Graph construction with junction detection
- Self-loop and zero-length edge cleanup
- Graph to GeoJSON export
- Coordinate snapping precision

#### Routing Service Tests (test_routing_service.py)

- find_nearest_node() - spatial queries
- build_graph_for_floors() - graph construction from DB
- calculate_route() - pathfinding success/failure
- Cross-building routing rejection
- No active graph version error
- No path found scenarios
- Multi-floor step generation
- Legacy function compatibility

#### Graph Workflow Tests (test_graph_workflow.py)

- _safe_name() helper for vertical node detection
- _distance_meters() calculation
- Floor stitching by name matching
- Fallback to nearest-node stitching
- Graph preview building (single/multi-floor)
- Graph confirmation with versioning
- Rollback to previous version
- Edge cases: empty buildings, no previous version

### Integration Tests

#### Navigation API (test_navigation_api.py)

- Successful route calculation
- Invalid UUID format handling
- Non-existent POI (404)
- Missing graph version (404)
- No path found (404)
- Internal server errors (500)
- Request/response model validation
- Coordinate validation (including negative values)

#### Graph API (test_graph_api.py)

- Graph rebuild preview (POST /api/graphs/rebuild/{id})
- Graph confirmation (POST /api/graphs/confirm/{id})
- Graph rollback (POST /api/graphs/rollback/{id})
- Invalid building ID (400)
- Building not found (404)
- No floors error (404)
- Empty graph handling
- Multi-floor stitching in preview
- Concurrent rebuild calls

#### Buildings/Floors API (test_buildings_api.py)

- Building CRUD operations
- Floor creation with GeoJSON
- Floor update with new GeoJSON
- Floor map retrieval
- Complex GeoJSON features (corridors, doors, rooms, stairs)
- Negative level numbers (basements)
- Empty FeatureCollection handling
- Missing field validation (422)
- Malformed JSON handling (400)

## Run Tests

```bash
source nav-service/bin/activate
python -m pytest tests/unit/ -q
python -m pytest tests/integration/ -q
python -m pytest tests/ -v
```

## Documentation Files

Project documents and long-form drafts are currently under `drafts/`.

