
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
./nav-service/bin/pip install -r requirements.txt.py
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

## Tests

```bash
source nav-service/bin/activate
python -m pytest tests/unit/ -q
python -m pytest tests/integration/ -q
python -m pytest tests/ -v
```

## Documentation Files

Project documents and long-form drafts are currently under `drafts/`.

