
## API Documentation

Full API reference is available in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).
Includes a Postman setup section and end-to-end request flow.


```
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

```
indoor_navigation_backend/
│
├─ app/
│   ├─ main.py             # FastAPI app entrypoint
│   ├─ database.py         # DB connection
│   ├─ models.py           # SQLAlchemy models
│   ├─ schemas.py          # Pydantic schemas
│   ├─ crud.py             # DB operations
│   ├─ routes/
│   │   ├─ map_routes.py       # floor/building/POI APIs
│   │   ├─ positioning_routes.py # live position APIs
│   │   └─ navigation_routes.py # route calculation APIs
│   └─ services/
│       ├─ routing_service.py   # Dijkstra/A* implementation
│       └─ positioning_service.py
│
├─ requirements.txt
└─ alembic/ (required for migrations)
```


Dependencies
```
pip install fastapi uvicorn[standard] sqlalchemy asyncpg psycopg2-binary pydantic geoalchemy2 networkx
```
- FastAPI → backend framework
- SQLAlchemy + asyncpg → DB + async support
- GeoAlchemy2 → spatial support for PostGIS
- NetworkX → graph algorithms (A*/Dijkstra) for routing


Database Setup (PostgreSQL + PostGIS)

```
CREATE DATABASE indoor_navigation;
\c indoor_navigation

-- Enable PostGIS
CREATE EXTENSION postgis;

-- Example table
CREATE TABLE floors (
    id UUID PRIMARY KEY,
    building_id UUID,
    level_number INT,
    name TEXT,
    height_meters FLOAT,
    floor_geojson JSONB
);
```



Refrences :
https://eng-badrqabbari.medium.com/using-dijkstras-algorithm-for-indoor-navigation-in-a-flutter-app-3d346c0ede23
https://www.researchgate.net/publication/349495339_A_New_Approach_to_Measuring_the_Similarity_of_Indoor_Semantic_Trajectories
https://www.researchgate.net/publication/341465979_The_Construction_of_a_Network_for_Indoor_Navigation


## Test Coverage

### Unit Tests

#### Pipeline Tests (`test_pipeline.py`)
- GeoJSON loading and validation (empty, invalid, non-FeatureCollection)
- Feature classification (corridors, doors, rooms, stairs)
- Graph construction with junction detection
- Self-loop and zero-length edge cleanup
- Graph to GeoJSON export
- Coordinate snapping precision

#### Routing Service Tests (`test_routing_service.py`)
- `find_nearest_node()` - spatial queries
- `build_graph_for_floors()` - graph construction from DB
- `calculate_route()` - pathfinding success/failure
- Cross-building routing rejection
- No active graph version error
- No path found scenarios
- Multi-floor step generation
- Legacy function compatibility

#### Graph Workflow Tests (`test_graph_workflow.py`)
- `_safe_name()` helper for vertical node detection
- `_distance_meters()` calculation
- Floor stitching by name matching
- Fallback to nearest-node stitching
- Graph preview building (single/multi-floor)
- Graph confirmation with versioning
- Rollback to previous version
- Edge cases: empty buildings, no previous version

### Integration Tests

#### Navigation API (`test_navigation_api.py`)
- Successful route calculation
- Invalid UUID format handling
- Non-existent POI (404)
- Missing graph version (404)
- No path found (404)
- Internal server errors (500)
- Request/response model validation
- Coordinate validation (including negative values)

#### Graph API (`test_graph_api.py`)
- Graph rebuild preview (`POST /api/graphs/rebuild/{id}`)
- Graph confirmation (`POST /api/graphs/confirm/{id}`)
- Graph rollback (`POST /api/graphs/rollback/{id}`)
- Invalid building ID (400)
- Building not found (404)
- No floors error (404)
- Empty graph handling
- Multi-floor stitching in preview
- Concurrent rebuild calls

#### Buildings/Floors API (`test_buildings_api.py`)
- Building CRUD operations
- Floor creation with GeoJSON
- Floor update with new GeoJSON
- Floor map retrieval
- Complex GeoJSON features (corridors, doors, rooms, stairs)
- Negative level numbers (basements)
- Empty FeatureCollection handling
- Missing field validation (422)
- Malformed JSON handling (400)

## To Run Tests

```bash
# Install test dependencies
./nav-service/bin/pip install -r requirements-test.txt

# Run all tests
pytest tests/ -v

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

