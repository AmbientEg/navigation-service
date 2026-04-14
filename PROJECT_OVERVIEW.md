# Indoor Navigation Backend - Project Overview

## 🎯 Project Purpose

This is a **FastAPI-based indoor navigation service** that provides routing and navigation capabilities for indoor spaces (buildings, floors, POIs). It uses graph-based algorithms (Dijkstra/A*) to calculate optimal routes between locations within buildings, with support for multi-floor navigation and spatial data management via PostGIS.

**Core Domain Intent:**
- Store indoor floor maps as GeoJSON in the database
- Build navigation graphs from GeoJSON (derived data)
- Version graph snapshots per building
- Route users using only the active graph version

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
│                      (main.py)                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Navigation API  │  │   Buildings API  │               │
│  │  (routes)        │  │   (routes)       │               │
│  ├──────────────────┤  ├──────────────────┤               │
│  │  Floors API      │  │   Graphs API     │               │
│  │  (routes)        │  │   (routes)       │               │
│  └────────┬─────────┘  └────────┬─────────┘               │
│           │                     │                          │
│  ┌────────▼─────────────────────▼──────────┐              │
│  │         Services Layer                   │              │
│  │  ┌──────────────────────────────────┐   │              │
│  │  │ Routing Service (graph algorithms)   │              │
│  │  │ Graph Workflow Service (versioning)  │              │
│  │  │ Graph Persistence Service           │              │
│  │  │ CRS Service (coordinate transforms)  │              │
│  │  └──────────────────────────────────┘   │              │
│  └────────┬─────────────────────────────────┘              │
│           │                                                │
│  ┌────────▼──────────────────────────────┐                │
│  │    Database Layer (SQLAlchemy ORM)    │                │
│  │    PostgreSQL + PostGIS               │                │
│  │    Alembic Migrations                 │                │
│  └───────────────────────────────────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

### Root Level Files
- **main.py** - FastAPI application entry point with middleware, exception handlers, and health checks
- **database.py** - Database connection management and async session factory
- **.env** - Environment variables (DATABASE_URL, ADMIN_API_TOKEN)
- **requirements.txt.py** - Dependencies (currently empty)

### `/models` - Data Models (SQLAlchemy ORM)
Core data entities representing the indoor navigation domain:

| Model | Purpose |
|-------|---------|
| **Building** | Represents a physical building with metadata |
| **Floor** | Represents a floor within a building with GeoJSON geometry |
| **RoutingNode** | Graph nodes representing waypoints/intersections in navigation |
| **RoutingEdge** | Graph edges representing connections between nodes with weights |
| **NodeType** | Classification of nodes (e.g., entrance, corridor, room, stairwell) |
| **EdgeType** | Classification of edges (e.g., corridor, stairs, elevator, ramp) |
| **POI** | Points of Interest (rooms, facilities, landmarks) |
| **NavigationGraphVersion** | Versioned snapshots of navigation graphs per building |

**Base Classes:**
- `Base` - SQLAlchemy declarative base
- `TimestampMixin` - Adds created_at/updated_at timestamps to models

**Graph Versioning:**
- Each building can have multiple graph versions
- Only one version is marked as `is_active` per building
- Nodes and edges are scoped to a specific `graph_version_id`
- Enables safe graph updates and rollback capability

### `/services` - Business Logic Layer

#### **routing_service.py**
Core routing engine for pathfinding:
- `find_nearest_node()` - Locates closest graph node to a given coordinate (constrained by graph_version_id)
- `build_graph_for_floors()` - Constructs NetworkX graph from database nodes/edges for a specific version
- `calculate_route()` - Implements Dijkstra/A* algorithm for route calculation (blocks cross-building routes)
- `generate_steps()` - Converts graph path into human-readable navigation steps
- `build_graph()` - Helper to construct NetworkX graph structure

#### **graph_workflow_service.py**
Manages graph versioning and lifecycle:
- `build_graph_preview_for_building()` - Builds in-memory graph preview from all floors
- `confirm_graph_preview()` - Persists preview as new graph version and activates it
- `rollback_to_previous_graph_version()` - Switches active version to previous one
- `get_active_graph_version()` - Retrieves currently active graph for a building
- **Stitching behavior:** Automatically connects adjacent floors, prefers vertical-node name matching (stairs/elevator/lift), falls back to nearest-node pair

#### **graph_persistence_service.py**
Handles loading/saving navigation graphs:
- `_load_json()` - Loads GeoJSON files
- `_point_wkt_from_xy()` - Converts coordinates to WKT format for PostGIS
- `_build_building_footprint_wkt()` - Creates building geometry from floor data
- `_get_or_create_building()` - Database operations for buildings
- `_get_or_create_floor()` - Database operations for floors

#### **crs_service.py**
Coordinate Reference System transformations:
- `utm_to_wgs84()` - Converts UTM coordinates to WGS84 (lat/lon)
- `looks_like_wgs84()` / `looks_like_utm()` - Detects coordinate system
- Transformer caching for performance

### `/routes` - API Endpoints

#### **navigation_routes.py**
Public navigation API:
- **POST /api/navigation/route** - Calculate route between two points
  - Request: `RouteRequest` (from_coords, to_coords, floor_id, options)
  - Response: Route with steps, distance, duration
  - Validates source floor and destination POI are in same building
  - Requires active graph version
- **GET /api/navigation/nearest-node** - Find nearest navigation node
- **GET /api/navigation/floors/{floor_id}** - Get floor geometry and nodes

#### **buildings_routes.py**
Building management endpoints:
- **POST /api/buildings** - Create building
- **GET /api/buildings/{building_id}** - Get building details
- **GET /api/buildings/{building_id}/floors** - List floors in building

#### **floors_routes.py**
Floor management endpoints:
- **POST /api/floors** - Create floor with GeoJSON
- **PUT /api/floors/{floor_id}** - Update floor GeoJSON
- **GET /api/floors/{floor_id}/map** - Get floor geometry and nodes

#### **graph_routes.py**
Graph versioning and management:
- **POST /api/graphs/rebuild/{building_id}** - Build preview graph from all floors
- **POST /api/graphs/confirm/{building_id}** - Confirm preview and activate as new version
- **POST /api/graphs/rollback/{building_id}** - Rollback to previous graph version
- **GET /api/graphs/{building_id}/active** - Get active graph version
- **GET /api/graphs/{building_id}/versions** - List all versions for building

#### **admin_auth.py**
Authentication middleware:
- `require_admin()` - Decorator to validate admin API token

### `/pipeline` - Data Processing Pipeline
Scripts for building navigation graphs from raw floor data:

| Script | Purpose |
|--------|---------|
| **step0_reproject.py** | Reproject floor GeoJSON to UTM coordinates |
| **step1_draw_Centerlines.py** | Extract corridor centerlines from floor polygons using medial axis/skeleton algorithms |
| **step2_construct_graph.py** | Build navigation graph from centerlines (nodes at junctions, edges along corridors) |
| **step3_verify_graph.py** | Validate graph integrity (edge weights, node coordinates, vertical movement) |
| **step4_persist_graph.py** | Save graph to database |
| **run_graph_pipeline.py** | Orchestrates all pipeline steps |

**Centerline Strategies:**
- `CenterLineStrategy` - Base strategy
- `TCorridorStrategy` - T-shaped corridor handling
- `LCorridorStrategy` - L-shaped corridor handling

### `/drafts` - Experimental Code
Development/testing scripts:
- Skeleton extraction algorithms
- Voronoi diagram approaches
- Tutorial scripts (geopandas, networkx)
- Route testing scripts

### `/postman` - API Testing
- `navigation-service.postman_collection.json` - API endpoint definitions
- `navigation-service.postman_environment.json` - Environment variables for testing

### Test Files
- **tests/conftest.py** - Pytest configuration with comprehensive fixtures
  - GeoJSON fixtures (corridors, doors, rooms, junctions, stairs)
  - Mock model fixtures (buildings, floors, POIs, graph versions)
  - Async database session mocks
  - NetworkX graph fixtures (connected, disconnected, multi-floor, with self-loops)
  - Test data fixtures (valid/invalid route requests)
- **tests/unit/** - Unit tests for individual services and utilities
- **tests/integration/** - Integration tests for API endpoints and workflows
- **requirements-test.txt** - Test dependencies (pytest, pytest-asyncio, pytest-cov, httpx)

---

## 🔄 Data Flow

### 1. **Data Ingestion Pipeline**
```
Raw Floor GeoJSON
    ↓
[step0] Reproject to UTM
    ↓
[step1] Extract Centerlines (medial axis)
    ↓
[step2] Build Navigation Graph (nodes + edges)
    ↓
[step3] Verify Graph Integrity
    ↓
[step4] Persist to Database
```

### 2. **Graph Versioning Workflow**
```
Update Floor GeoJSON
    ↓
[Rebuild] Build preview graph in memory from all floors
    ↓
[Confirm] Persist preview as new graph version
    ↓
[Activate] Mark new version as is_active
    ↓
[Stitch] Connect adjacent floors (vertical edges)
    ↓
Ready for routing
```

### 3. **Route Calculation Flow**
```
User Request (from_coords, to_coords, floor_id)
    ↓
[Validate] Check same building, active version exists
    ↓
[Find Nearest Nodes] Snap user coords to graph nodes (version-scoped)
    ↓
[Build Graph] Load nodes/edges from database for active version
    ↓
[Dijkstra/A*] Calculate shortest path
    ↓
[Generate Steps] Convert path to navigation instructions
    ↓
Response (route, distance, duration, turn-by-turn)
```

### 4. **Rollback Workflow**
```
Issues detected with active graph
    ↓
[Rollback] Switch is_active to previous version
    ↓
Routing uses previous version
    ↓
Can rebuild and confirm new version later
```

---

## 🗄️ Database Schema

**PostgreSQL + PostGIS** with async support via asyncpg

### Key Tables
- `buildings` - Building metadata with geometry
- `floors` - Floor data with GeoJSON geometry (source of truth)
- `routing_nodes` - Navigation waypoints (Point geometry, version-scoped)
- `routing_edges` - Connections between nodes (LineString geometry, version-scoped)
- `node_types` - Node classifications
- `edge_types` - Edge classifications
- `pois` - Points of Interest
- `navigation_graph_versions` - Versioned graph snapshots per building

**Spatial Features:**
- PostGIS extension for geometric operations
- WKT (Well-Known Text) format for geometry storage
- Coordinate transformations (WGS84 ↔ UTM)
- Spatial queries (ST_Distance, ST_AsText) for node location

### Database Migrations
- **Alembic** for schema versioning and migrations
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Migration environment setup
- `alembic/versions/` - Migration scripts
  - `001_initial_schema.py` - Initial schema
  - `6845ad39a047_baseline_schema_20260330.py` - Baseline schema
  - `7c24d182ba01_graph_versioning_managed.py` - Graph versioning support

**Important Note:**
- `Base.metadata.create_all()` creates missing tables but does not perform full schema migrations
- Use Alembic for all schema changes: `alembic revision`, `alembic upgrade head`

---

## 🔧 Key Technologies

| Component | Technology |
|-----------|-----------|
| **Framework** | FastAPI (async Python web framework) |
| **Database** | PostgreSQL + PostGIS (spatial database) |
| **ORM** | SQLAlchemy (async support via asyncpg) |
| **Graph Algorithms** | NetworkX (Dijkstra, A*, graph operations) |
| **Geospatial** | GeoPandas, Shapely (geometry operations) |
| **Coordinate Transforms** | Pyproj (CRS transformations) |
| **Server** | Uvicorn (ASGI server) |

---

## 🚀 API Endpoints Summary

### Navigation Endpoints
```
POST   /api/navigation/route              Calculate route between points
GET    /api/navigation/nearest-node       Find nearest node to coordinates
GET    /api/navigation/floors/{id}        Get floor geometry and nodes
```

### Building Endpoints
```
POST   /api/buildings                     Create building
GET    /api/buildings/{building_id}       Get building details
GET    /api/buildings/{building_id}/floors List floors in building
```

### Floor Endpoints
```
POST   /api/floors                        Create floor with GeoJSON
PUT    /api/floors/{floor_id}             Update floor GeoJSON
GET    /api/floors/{floor_id}/map         Get floor geometry and nodes
```

### Graph Management Endpoints
```
POST   /api/graphs/rebuild/{building_id}  Build preview graph from all floors
POST   /api/graphs/confirm/{building_id}  Confirm preview and activate as new version
POST   /api/graphs/rollback/{building_id} Rollback to previous graph version
GET    /api/graphs/{building_id}/active   Get active graph version
GET    /api/graphs/{building_id}/versions List all versions for building
```

### Health & Status
```
GET    /health                            Overall health check
GET    /health/ready                      Readiness probe
GET    /health/live                       Liveness probe
GET    /api/status                        API status
```

---

## 🔐 Security Features

- **CORS Middleware** - Configurable cross-origin requests
- **Trusted Host Middleware** - Production host validation
- **Security Headers** - CSP, X-Frame-Options, X-Content-Type-Options
- **Admin Authentication** - API token validation
- **Request Logging** - Correlation IDs for tracing
- **Exception Handling** - Secure error responses (no internal details in production)

---

## 📝 Configuration

### Environment Variables (.env)
```
DATABASE_URL=postgresql://user:pass@host/db    # Required
ENVIRONMENT=production|development              # Optional
LOG_LEVEL=INFO|DEBUG|WARNING                   # Optional
CORS_ORIGINS=*|https://example.com             # Optional
ALLOWED_HOSTS=*|example.com                    # Optional
AWS_LAMBDA_FUNCTION_NAME=                      # Optional, if running in Lambda
ADMIN_API_TOKEN=your-secret-token              # Optional, for admin endpoints
```

### Database Connection
- Uses asyncpg for async PostgreSQL support
- Connection pooling (pool_size=20, max_overflow=30)
- Automatic connection recycling (3600s)
- Pre-ping enabled for stale connection detection
- Auto-converts `postgresql://` to `postgresql+asyncpg://`
- Strips unsupported asyncpg URL params (sslmode, channel_binding, gssencmode)

### Running the Application
```bash
# Activate virtual environment
source nav-service/bin/activate

# Install dependencies (if needed)
./nav-service/bin/pip install -r requirements.txt

# Run development server
./nav-service/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Alternative port if 8000 is occupied
./nav-service/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010

# Test database connection
./nav-service/bin/python database.py
```

### Database Setup
```sql
-- Create database
CREATE DATABASE navigationDB;

-- Connect to database
\c navigationDB

-- Enable PostGIS extension
CREATE EXTENSION postgis;

-- Run migrations
alembic upgrade head
```

---

## 🧪 Testing

### Test Structure
- **tests/conftest.py** - Comprehensive pytest fixtures for all test types
- **tests/unit/** - Unit tests for services, utilities, and models
- **tests/integration/** - Integration tests for API endpoints and workflows

### Available Fixtures
- **GeoJSON Fixtures:** Simple corridors, corridors with doors/rooms, multi-corridor junctions, stairs connectors, empty/invalid GeoJSON
- **Mock Models:** Buildings, floors, POIs, graph versions, node/edge types
- **Database:** Async session mocks
- **Graphs:** Connected, disconnected, multi-floor, with self-loops, with zero-weight edges
- **Request Data:** Valid/invalid route requests

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/unit/test_routing_service.py

# Run with verbose output
pytest -v
```

### Test Dependencies
- pytest >= 7.0.0
- pytest-asyncio >= 0.21.0
- pytest-cov >= 4.0.0
- httpx >= 0.24.0 (for async TestClient support)

---

## 📚 References & Algorithms

### Routing Algorithms
- **Dijkstra's Algorithm** - Shortest path calculation
- **A* Algorithm** - Heuristic-based pathfinding
- **Medial Axis Transform** - Centerline extraction from polygons

### Research Papers Referenced
- [Dijkstra's Algorithm for Indoor Navigation](https://eng-badrqabbari.medium.com/using-dijkstras-algorithm-for-indoor-navigation-in-a-flutter-app-3d346c0ede23)
- [Indoor Semantic Trajectories Similarity](https://www.researchgate.net/publication/349495339_A_New_Approach_to_Measuring_the_Similarity_of_Indoor_Semantic_Trajectories)
- [Network Construction for Indoor Navigation](https://www.researchgate.net/publication/341465979_The_Construction_of_a_Network_for_Indoor_Navigation)

---

## 🎯 Workflow Summary

### 1. **Initial Setup**
- Create PostgreSQL database with PostGIS extension
- Run Alembic migrations: `alembic upgrade head`
- Configure `.env` with DATABASE_URL and other settings
- Start FastAPI server

### 2. **Data Preparation**
- Prepare floor GeoJSON files (source of truth)
- Use pipeline scripts to validate and process GeoJSON
- Upload floors via `/api/floors` endpoint

### 3. **Graph Building**
- Call `/api/graphs/rebuild/{building_id}` to build preview graph from all floors
- Verify graph integrity (nodes, edges, connectivity)
- Call `/api/graphs/confirm/{building_id}` to activate new version
- System automatically stitches adjacent floors with vertical edges

### 4. **Route Queries**
- Users request routes via `/api/navigation/route`
- System validates same building, uses active graph version
- Calculates shortest path using Dijkstra/A*
- Returns turn-by-turn navigation steps

### 5. **Graph Updates**
- Update floor GeoJSON via `/api/floors/{floor_id}`
- Rebuild graph preview
- Confirm new version (old version remains available)
- If issues detected, rollback to previous version

### 6. **Monitoring**
- Health checks: `/health`, `/health/ready`, `/health/live`
- Request logging with correlation IDs
- Database connection monitoring
- Graph statistics and version tracking

---

## 🔄 Lifespan Management

The application uses FastAPI's lifespan context manager for:
- **Startup** - Initialize database, create tables, run migrations
- **Shutdown** - Close database connections, cleanup resources

Supports both traditional server mode and AWS Lambda deployment.

---

## 📊 Graph Structure

Navigation graphs consist of:
- **Nodes** - Waypoints with coordinates, types (entrance, corridor, room, etc.), version-scoped
- **Edges** - Connections with weights (distance), types (corridor, stairs, elevator, etc.), version-scoped
- **Attributes** - Floor ID, building ID, accessibility info, restrictions
- **Vertical Edges** - Connect adjacent floors (stairs, elevators, lifts)

Graphs are built from floor centerlines and can span multiple floors with automatic stitching.

---

## 🔐 Data Separation & Integrity

**Source of Truth:**
- `floors.floor_geojson` - Raw GeoJSON FeatureCollection (authoritative input)

**Derived Data:**
- `routing_nodes` + `routing_edges` - Computed from floor GeoJSON
- `navigation_graph_versions` - Versioned snapshots per building

**Key Principle:**
- Never manually mutate derived graph data
- Always update source floor GeoJSON and rebuild graph
- Use rebuild/confirm workflow for safe updates
- Keep one active graph version per building

---

## 🔧 Tech Stack Details

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI | Async Python web framework |
| **Database** | PostgreSQL + PostGIS | Spatial database with geometry support |
| **ORM** | SQLAlchemy 2.x | Async ORM with asyncpg driver |
| **Migrations** | Alembic | Schema versioning and migrations |
| **Graph Algorithms** | NetworkX | Dijkstra, A*, graph operations |
| **Geospatial** | GeoPandas, Shapely | Geometry operations and analysis |
| **Coordinate Transforms** | Pyproj | CRS transformations (WGS84 ↔ UTM) |
| **Server** | Uvicorn | ASGI server |
| **Testing** | Pytest, pytest-asyncio | Async test framework |
| **Async Support** | asyncpg, greenlet | Async PostgreSQL driver |

---

## 📚 References & Algorithms

### Routing Algorithms
- **Dijkstra's Algorithm** - Shortest path calculation
- **A* Algorithm** - Heuristic-based pathfinding
- **Medial Axis Transform** - Centerline extraction from polygons

### Research Papers Referenced
- [Dijkstra's Algorithm for Indoor Navigation](https://eng-badrqabbari.medium.com/using-dijkstras-algorithm-for-indoor-navigation-in-a-flutter-app-3d346c0ede23)
- [Indoor Semantic Trajectories Similarity](https://www.researchgate.net/publication/349495339_A_New_Approach_to_Measuring_the_Similarity_of_Indoor_Semantic_Trajectories)
- [Network Construction for Indoor Navigation](https://www.researchgate.net/publication/341465979_The_Construction_of_a_Network_for_Indoor_Navigation)

---

## 📖 Additional Documentation

- **CLAUDE.md** - Project-specific guidance for developers
- **API_DOCUMENTATION.md** - Detailed API endpoint documentation
- **ARCHITECTURE_WORKFLOW.md** - Architecture and workflow diagrams
- **README.md** - Project setup and overview
- **Postman Collections** - API testing assets in `/postman`

---

*Last Updated: March 2026*
