# Implementation Plan: Navigation Service Workflow + Graph Pipeline Integration

## Current Status Summary

**✅ Already In Place:**
- All core data models (`RoutingNode`, `RoutingEdge`, `EdgeType`, `NodeType`, `Floor`, `Building`)
- Routing service that reads from DB → builds graph → calculates route
- Basic API endpoints for retrieving buildings/floors/routes
- Pipeline steps (step0-3) that construct graph from GeoJSON
- `POST /api/navigation/route` working end-to-end

**❌ Missing Components:**
- CRUD endpoints (create building, create/update floor)
- Graph versioning model + endpoints
- Pipeline refactor (currently file-based, needs in-memory GeoJSON support)
- Graph persistence service (converts GeoJSON → DB nodes/edges)
- Admin preview/confirm workflow

---

## Implementation Plan (7 Phases)

### **Phase 1: Add Graph Versioning Model**
**Goal:** Track graph versions and mark active version

**Create:** `models/navigation_graph_version.py`
```python
class NavigationGraphVersion(Base, TimestampMixin):
    id: UUID
    building_id: FK→Building
    is_active: bool (default=True)
    
    - When new version confirmed, set all other building versions to is_active=False
```

**Deliverable:** 1 new model class

---

### **Phase 2: Create Graph Persistence Service**
**Goal:** Convert GeoJSON features → DB nodes/edges

**Create:** `services/graph_persistence_service.py`

**Functions:**
```python
async def persist_graph_from_geojson(
    db: AsyncSession,
    floor_id: UUID,
    geojson: dict,
    clear_existing: bool = True
) -> dict:
    """
    Parse GeoJSON, extract nodes/edges, persist to DB.
    
    Steps:
    1. Clear old nodes/edges for floor (if clear_existing=True)
    2. Extract Point features → create RoutingNodes
    3. Extract LineString features → create RoutingEdges
    4. Return summary: {nodes_created, edges_created}
    """
```

**Deliverable:** 1 service module with async functions

---

### **Phase 3: Refactor Pipeline to Accept In-Memory GeoJSON**
**Goal:** Remove file dependency, accept GeoJSON dict as input

**Refactor:** `pipeline/step2_construct_graph.py` + `pipeline/step3_verify_graph.py`

**New function signatures:**
```python
def step2_construct_graph(geojson: dict, floor_id: str) -> nx.Graph:
    """Build graph from GeoJSON dict (instead of local file)"""

def step3_verify_graph(graph: nx.Graph) -> nx.Graph:
    """Verify graph in-memory (already done, but ensure no file I/O)"""

def export_graph_to_geojson(graph: nx.Graph) -> dict:
    """Return graph as GeoJSON dict (not file)"""
```

**Deliverable:** Refactored pipeline that's testable and in-memory

---

### **Phase 4: Add CRUD Endpoints (Buildings & Floors)**
**Goal:** Allow admin to create buildings and floors with GeoJSON

**Create:** `routes/buildings_routes.py` additions + `routes/floors_routes.py` additions

**Endpoints:**

#### 4.1 `POST /api/buildings`
```json
{
  "name": "Physics Building",
  "description": "Main physics wing",
  "floors_count": 3
}
```
Response: `{id, name, description, floors_count, created_at}`

#### 4.2 `POST /api/floors`
```json
{
  "building_id": "uuid",
  "level_number": 1,
  "name": "Ground Floor",
  "height_meters": 3.5,
  "floor_geojson": { ...GeoJSON FeatureCollection... }
}
```
Response: `{id, building_id, level_number, name, height_meters, floor_geojson, created_at}`

#### 4.3 `PUT /api/floors/{floor_id}`
```json
{
  "floor_geojson": { ...updated GeoJSON... }
}
```
Response: Updated floor object

**Deliverable:** 3 new endpoints (POST/POST/PUT)

---

### **Phase 5: Add Graph Rebuild API (Preview)**
**Goal:** Rebuild graph from floor GeoJSON, return preview (DON'T save yet)

**Create:** `routes/graph_routes.py`

#### 5.1 `POST /api/buildings/{building_id}/graph/rebuild`
- Fetch all floors for building from DB
- For each floor: run pipeline on `floor.floor_geojson`
- Stitch multi-floor graph
- Return preview without persisting

**Response:**
```json
{
  "status": "preview",
  "graphs": {
    "floor_1": {
      "nodes": [
        {
          "id": "node-1",
          "lat": 30.0444,
          "lng": 31.2357,
          "node_type": "corridor",
          "floor_id": "uuid"
        }
      ],
      "edges": [
        {
          "from": "node-1",
          "to": "node-2",
          "distance": 42.5,
          "edge_type": "hallway"
        }
      ]
    }
  },
  "summary": {
    "total_nodes": 150,
    "total_edges": 280,
    "floors_processed": 3
  }
}
```

**Deliverable:** 1 endpoint for preview

---

### **Phase 6: Add Graph Confirm & Persist API**
**Goal:** Save preview to DB, mark version as active

#### 6.1 `POST /api/buildings/{building_id}/graph/confirm`
**Flow:**
1. Create new `NavigationGraphVersion` entry with `is_active=False`
2. Call `graph_persistence_service.persist_graph_from_geojson()` for each floor
3. Set `is_active=True` for new version
4. Set `is_active=False` for all other versions in building
5. Return confirmation

**Response:**
```json
{
  "status": "confirmed",
  "graph_version_id": "version-uuid",
  "is_active": true,
  "persisted": {
    "nodes": 450,
    "edges": 840,
    "floors": 3
  },
  "previous_active_version_id": "old-version-uuid"
}
```

**Deliverable:** 1 endpoint for confirmation + persistence

---

### **Phase 7: Update Routing Service to Use Active Graph Version**
**Goal:** Ensure routing always uses active graph

**Refactor:** `services/routing_service.py`

**Changes:**
```python
async def build_graph_for_floors(
    db: AsyncSession,
    building_id: UUID,  # Add building context
    floor_ids: List[UUID],
    accessible_only: bool = False
) -> nx.Graph:
    # Query: SELECT * FROM routing_nodes 
    #        WHERE floor_id IN (floor_ids)
    #        AND EXISTS (
    #          SELECT 1 FROM navigation_graph_versions 
    #          WHERE building_id = ?
    #          AND is_active = true
    #        )
```

**Deliverable:** Updated routing logic with version awareness

---

## Implementation Sequence (Recommended)

1. **Phase 1** (5 min) - Create `NavigationGraphVersion` model
2. **Phase 3** (20 min) - Refactor pipeline to in-memory
3. **Phase 2** (30 min) - Build persistence service
4. **Phase 4** (20 min) - Add CRUD endpoints
5. **Phase 5** (30 min) - Build rebuild endpoint + preview
6. **Phase 6** (20 min) - Build confirm endpoint
7. **Phase 7** (15 min) - Update routing service

**Total Estimated Time:** ~2 hours

---

## Testing Strategy

Each phase should have:
- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test endpoint-to-endpoint workflow
- **Example data**: Use `floor3.geojson` as test data

---

## Key Design Decisions

✅ **GeoJSON = Source of Truth**
- Always stored in `Floor.floor_geojson`
- Never directly edited in nodes/edges

✅ **Routing Nodes/Edges = Derived**
- Built from GeoJSON via pipeline
- Only created/updated during graph rebuild

✅ **Graph Rebuild = Manual + Previewed**
- Not automatic on GeoJSON change
- Admin sees preview first
- Must confirm to persist

✅ **Active Graph = Single Version**
- Only one version `is_active=true` per building
- Routing always uses active version
- Can rollback to previous version later (future feature)

---

## Error Handling

| Error | Status | Message |
|-------|--------|---------|
| Invalid GeoJSON syntax | 400 | "Invalid GeoJSON format" |
| Missing required fields | 400 | "Missing required fields: {list}" |
| Building/Floor not found | 404 | "Building/Floor not found" |
| Pipeline failed | 500 | "Graph rebuild failed: {details}" |
| No route possible | 404 | "Cannot calculate route with current graph" |

