# Indoor Navigation API Documentation

## Base URL
- Local: http://127.0.0.1:8000

## Postman Documentation

### Postman Environment
Create a Postman environment with these variables:

- `baseUrl` = `http://127.0.0.1:8000`
- `buildingId` = (empty)
- `floorId` = (empty)
- `poiId` = (set to an existing POI UUID before route testing)

### Recommended Collection Structure

Create a collection named `Indoor Navigation API` and add folders:

1. `Health`
2. `Buildings`
3. `Floors`
4. `Graphs`
5. `Navigation`

### End-to-End Postman Flow

Run requests in this order.

1. `GET {{baseUrl}}/health`
2. `POST {{baseUrl}}/api/buildings`
3. `POST {{baseUrl}}/api/floors`
4. `PUT {{baseUrl}}/api/floors/{{floorId}}`
5. `POST {{baseUrl}}/api/graphs/rebuild/{{buildingId}}`
6. `POST {{baseUrl}}/api/graphs/confirm/{{buildingId}}`
7. `POST {{baseUrl}}/api/navigation/route`
8. `POST {{baseUrl}}/api/graphs/rollback/{{buildingId}}` (optional)

### Postman Tests (Save IDs Automatically)

Use these snippets in the Postman `Tests` tab.

For `POST /api/buildings`:
```javascript
pm.test("building created", function () {
  pm.response.to.have.status(200);
});

const body = pm.response.json();
if (body && body.id) {
  pm.environment.set("buildingId", body.id);
}
```

For `POST /api/floors`:
```javascript
pm.test("floor created", function () {
  pm.response.to.have.status(200);
});

const body = pm.response.json();
if (body && body.id) {
  pm.environment.set("floorId", body.id);
}
```

### Postman Request Bodies

Create Building:
```json
{
  "name": "Main Building",
  "description": "Campus building",
  "floors_count": 0,
  "geometry_wkt": "POLYGON((31.2 30.0, 31.21 30.0, 31.21 30.01, 31.2 30.01, 31.2 30.0))"
}
```

Create Floor:
```json
{
  "building_id": "{{buildingId}}",
  "level_number": 1,
  "name": "Floor 1",
  "height_meters": 3.0,
  "floor_geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

Update Floor GeoJSON:
```json
{
  "floor_geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

Route Request:
```json
{
  "from": {
    "floorId": "{{floorId}}",
    "lat": 30.0444,
    "lng": 31.2357
  },
  "to": {
    "poiId": "{{poiId}}"
  },
  "options": {
    "accessible": true
  }
}
```

### Postman Notes

- `poiId` must reference an existing POI in the same building as `floorId`.
- `PUT /api/floors/{floor_id}` does not rebuild the graph automatically.
- Rebuild and confirm graph after GeoJSON updates to make routing use the latest map.

## Core Design Rules
- GeoJSON is the source of truth and is stored in `floors.floor_geojson`.
- Navigation graph is derived data.
- Graph does not auto-rebuild when floor GeoJSON changes.
- Rebuild is manual, previewed, then confirmed.
- All graph versions are retained.
- Routing always uses the active graph version.

## Health Endpoints
- GET /health
- GET /health/ready
- GET /health/live

## Buildings API
Base: /api/buildings

### POST /api/buildings
Create building.

Request body:
```json
{
  "name": "Main Building",
  "description": "Campus building",
  "floors_count": 3,
  "geometry_wkt": "POLYGON((31.2 30.0, 31.21 30.0, 31.21 30.01, 31.2 30.01, 31.2 30.0))"
}
```

Notes:
- `geometry_wkt` must be POLYGON WKT.

### GET /api/buildings/{building_id}
Get building by UUID.

### GET /api/buildings/{building_id}/floors
List floors for building.

## Floors API
Base: /api/floors

### POST /api/floors
Create floor and store GeoJSON.

Request body:
```json
{
  "building_id": "11111111-1111-1111-1111-111111111111",
  "level_number": 1,
  "name": "Floor 1",
  "height_meters": 3.0,
  "floor_geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

### PUT /api/floors/{floor_id}
Replace floor GeoJSON map data.

Request body:
```json
{
  "floor_geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

Important:
- This endpoint does not rebuild graph automatically.

### GET /api/floors/{floor_id}/map
Returns floor map as GeoJSON FeatureCollection.

## Graph Workflow API
Base: /api/graphs

### POST /api/graphs/rebuild/{building_id}
Manual rebuild preview for all building floors.

Behavior:
- Reads all floor GeoJSON from DB.
- Builds per-floor graph in-memory.
- Always stitches adjacent floors.
- Returns preview as nodes and edges JSON.
- Does not persist.

Response shape:
```json
{
  "status": "preview",
  "building_id": "11111111-1111-1111-1111-111111111111",
  "nodes": [
    {
      "id": "floorUuid:n:1",
      "floor_id": "floorUuid",
      "floor_level": 1,
      "lng": 31.2,
      "lat": 30.0,
      "node_type": "corridor",
      "name": null,
      "space_type": null
    }
  ],
  "edges": [
    {
      "id": "floorUuid:e:1",
      "from": "floorUuid:n:1",
      "to": "floorUuid:n:2",
      "distance": 2.4,
      "edge_type": "corridor",
      "from_floor_id": "floorUuid",
      "to_floor_id": "floorUuid",
      "is_stitched": false
    }
  ],
  "summary": {
    "total_nodes": 120,
    "total_edges": 160,
    "stitched_edges": 2,
    "floors_processed": 3
  }
}
```

### POST /api/graphs/confirm/{building_id}
Confirm current graph by rebuilding and persisting as a new active version.

Behavior:
- Keeps all historical versions.
- Creates a new version with incremented version number.
- Deactivates previous active version.
- Persists nodes and edges with graph version reference.

Response shape:
```json
{
  "status": "confirmed",
  "graph_version_id": "22222222-2222-2222-2222-222222222222",
  "version_number": 4,
  "previous_active_version_id": "33333333-3333-3333-3333-333333333333",
  "persisted": {
    "nodes": 120,
    "edges": 160,
    "floors": 3
  }
}
```

### POST /api/graphs/rollback/{building_id}
Quick rollback to previous version.

Behavior:
- Marks current active version inactive.
- Marks previous version active.

Response shape:
```json
{
  "status": "rolled_back",
  "rolled_back_to_version_id": "44444444-4444-4444-4444-444444444444",
  "rolled_back_to_version_number": 3,
  "previous_active_version_id": "22222222-2222-2222-2222-222222222222",
  "previous_active_version_number": 4
}
```

## Navigation API
Base: /api/navigation

### POST /api/navigation/route
Calculate route from start coordinate to destination POI.

Request body:
```json
{
  "from": {
    "floorId": "11111111-1111-1111-1111-111111111111",
    "lat": 30.0444,
    "lng": 31.2357
  },
  "to": {
    "poiId": "22222222-2222-2222-2222-222222222222"
  },
  "options": {
    "accessible": true
  }
}
```

Behavior:
- Resolves building from source floor and destination POI floor.
- Loads active graph version for that building.
- Builds graph from versioned nodes/edges.
- Runs shortest path.

## Common Error Cases
- 400: Invalid UUID format.
- 404: Building/Floor/POI not found.
- 404: No previous graph version for rollback.
- 404: No active navigation graph version found.
- 500: Graph rebuild/confirm/rollback internal failure.
