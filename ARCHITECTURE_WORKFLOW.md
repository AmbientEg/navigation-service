# Navigation Service Architecture & Workflow

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ADMIN API LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  POST /api/buildings          POST /api/floors         PUT /api/floors   
│  (Create Building)            (Create Floor +          (Update Floor     
│  ↓                            GeoJSON)                  GeoJSON)          
│  Building Model               ↓                        ↓                 
│                               Floor Model              Floor Model       
│                               + floor_geojson         + floor_geojson   
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                     ↓
                    ┌────────────────────────────────┐
                    │   FLOOR GEOJSON (Source Truth) │
                    │   Stored in DB: Floor.geojson  │
                    └────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    GRAPH PIPELINE ADMIN WORKFLOW                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  POST /api/buildings/{id}/graph/rebuild                                  │
│  (Rebuild Graph - Preview Only)                                          │
│  ↓                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ 1. Fetch all floors for building from DB                    │       │
│  │ 2. For each floor: Run Pipeline(floor_geojson)      ←────┐  │       │
│  │    - step2: construct graph from centerlines         │    │  │       │
│  │    - step3: verify & clean graph                    │    │  │       │
│  │ 3. Stitch multi-floor graph                         │    │  │       │
│  │ 4. Return preview JSON (nodes + edges)          ←───┤    │  │       │
│  │ 5. Do NOT persist yet                           │    │  │  │       │
│  └──────────────────────────────────────────────────────┘│   │  │       │
│     Response: {nodes: [...], edges: [...], summary}  │   │  │  │       │
│                                                         │   │  │  │       │
│  ┌────────────────────────────────────────────────────┘   │  │       │
│  │                                                        │  │       │
│  ↓                                                        │  │       │
│  Admin Reviews Graph Preview                             │  │       │
│  (Visualizes in frontend)                               │  │       │
│  ↓                                                        │  │       │
│  POST /api/buildings/{id}/graph/confirm                 │  │       │
│  (Confirm & Persist - Save to DB)                       │  │       │
│  ↓                                                        │  │       │
│  ┌──────────────────────────────────────────────────────┘   │       │
│  │ 1. Create new NavigationGraphVersion (is_active=false)    │       │
│  │ 2. Persist nodes/edges to DB:                             │       │
│  │    - Call graph_persistence_service.persist_graph(...)    │       │
│  │      For each floor: Convert GeoJSON → RoutingNode/Edge   │       │
│  │ 3. Set new version is_active=true                         │       │
│  │ 4. Set old versions is_active=false                       │       │
│  │ 5. Routing service now uses new active graph              │       │
│  └──────────────────────────────────────────────────────────┘       │
│     Response: {status: confirmed, persisted: {...}}                  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
        ┌──────────────────────────────────────┐
        │  ROUTING NODES & EDGES (Derived)     │
        │  - RoutingNode (Point Geometry)      │
        │  - RoutingEdge (Distance, Type)      │
        │  - EdgeType (hallway, stairs, ...)   │
        └──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         ROUTING SERVICE LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  POST /api/navigation/route                                              │
│  (Calculate Route Using Active Graph)                                    │
│  ↓                                                                        │
│  1. Query active NavigationGraphVersion for building                     │
│  2. Load active nodes/edges from DB                                      │
│  3. Build NetworkX graph from DB data                                    │
│  4. Dijkstra shortest path                                               │
│  5. Return route: {floors: [...], distance, steps}                       │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: End-to-End Example

### Scenario: Admin creates a new building with 2 floors

```
1. CREATE BUILDING
   POST /api/buildings
   {
     "name": "Physics Wing",
     "description": "Main physics department",
     "floors_count": 2
   }
   → Building created with id: <building-uuid>

2. ADD FLOOR 1 GeoJSON
   POST /api/floors
   {
     "building_id": "<building-uuid>",
     "level_number": 0,
     "name": "Ground Floor",
     "height_meters": 3.5,
     "floor_geojson": {
       "type": "FeatureCollection",
       "features": [
         {"geometry": {"type": "Point", "coordinates": [...]}, "properties": {...}},
         {"geometry": {"type": "LineString", "coordinates": [...]}, "properties": {...}},
         ...
       ]
     }
   }
   → Floor 0 created with id: <floor-uuid-0>

3. ADD FLOOR 2 GeoJSON
   POST /api/floors (similar structure)
   → Floor 1 created with id: <floor-uuid-1>

4. UPDATE FLOOR GeoJSON (if needed)
   PUT /api/floors/<floor-uuid-0>
   {
     "floor_geojson": { ...updated data... }
   }
   → Floor 0 updated (routing nodes still use old graph)

5. REBUILD GRAPH (Preview)
   POST /api/buildings/<building-uuid>/graph/rebuild
   → Pipeline runs in-memory on both floors' GeoJSON
   → Returns preview JSON (nodes + edges, not saved)
   
   Response:
   {
     "graphs": {
       "floor_0": {
         "nodes": [...],
         "edges": [...]
       },
       "floor_1": {
         "nodes": [...],
         "edges": [...]
       }
     },
     "summary": {"total_nodes": 150, "total_edges": 250}
   }

6. ADMIN REVIEWS PREVIEW
   Frontend visualizes the nodes/edges
   ✓ Looks good? Proceed
   ✗ Wrong? Modify floor GeoJSON, go to step 4

7. CONFIRM & PERSIST
   POST /api/buildings/<building-uuid>/graph/confirm
   → Creates NavigationGraphVersion (is_active=true)
   → Persists nodes/edges to RoutingNode/RoutingEdge tables
   → Old graph version set to is_active=false
   
   Response:
   {
     "status": "confirmed",
     "graph_version_id": "<version-uuid>",
     "persisted": {"nodes": 150, "edges": 250, "floors": 2}
   }

8. NOW ROUTING WORKS
   POST /api/navigation/route
   {
     "from": {"floorId": "<floor-uuid-0>", "lat": 30.04, "lng": 31.23},
     "to": {"poiId": "<poi-uuid>"},
     "options": {"accessible": true}
   }
   → Uses active graph (created in step 7)
   → Dijkstra finds path
   → Returns route with steps
```

---

## State Diagram: Graph Version Lifecycle

```
┌─────────────────┐
│  Graph v1       │
│  is_active=TRUE │ ← Routing uses this
│  created: t0    │
└─────────────────┘

  ↓ (Admin modifies floor GeoJSON + rebuilds)

┌─────────────────┐         ┌──────────────────┐
│  Graph v1       │         │  Graph v2        │
│  is_active=FALSE│ ◄─────► │  is_active=TRUE  │ ← Routing uses this
│  created: t0    │ (during)│  created: t1     │
└─────────────────┘         └──────────────────┘

  ↓ (Admin reverts to v1)

┌─────────────────┐         ┌──────────────────┐
│  Graph v1       │         │  Graph v2        │
│  is_active=TRUE │ ◄─────► │  is_active=FALSE │
│  created: t0    │ (during)│  created: t1     │
└─────────────────┘         └──────────────────┘
```

---

## Key Separation of Concerns

```
┌─────────────────────────────────────┐
│ ADMIN LAYER (Buildings/Floors CRUD) │
├─────────────────────────────────────┤
│ Responsibility: Manage spatial data │
│ Input: GeoJSON                      │
│ Output: Floor entity with GeoJSON   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ GRAPH PIPELINE (Rebuild/Confirm)    │
├─────────────────────────────────────┤
│ Responsibility: Convert GeoJSON → Graph
│ Input: floor_geojson (from Floor)   │
│ Output: nodes/edges to DB           │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ ROUTING SERVICE (Query)             │
├─────────────────────────────────────┤
│ Responsibility: Find path using     │
│ active graph                        │
│ Input: start coord, destination POI │
│ Output: route with steps            │
└─────────────────────────────────────┘
```

---

## Why This Design Works

✅ **GeoJSON = Single Source of Truth**
- Floors always store the authoritative spatial data
- No risk of GeoJSON/graph mismatch

✅ **Manual Graph Rebuild = Controlled**
- No accidental graph rebuilds
- Admin can review preview before committing
- Easy to rollback if graph is wrong

✅ **Versioning = Safety**
- Keep history of all graph versions
- Can revert to previous version if needed
- New versions don't break old routing

✅ **In-Memory Pipeline = No File I/O**
- Faster (no disk bottleneck)
- Testable (unit tests with dict input)
- Scalable (can rebuild multiple graphs in parallel)

✅ **Active Version = Consistent Routing**
- Routing service always uses one active graph
- No race conditions (one writer, many readers pattern)
- Easy to monitor (check which version is active)
