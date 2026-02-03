# Navigation Service API Documentation

## Overview
This navigation service provides APIs for indoor navigation, building management, and floor mapping. All endpoints are prefixed with `/api`.

## API Endpoints

### 🏢 Building APIs

#### Get Building
```
GET /api/buildings/{id}
```

**Description:** Retrieve detailed information about a specific building.

**Parameters:**
- `id` (path, required): UUID of the building

**Response:**
```json
{
  "id": "uuid",
  "name": "Building Name",
  "description": "Building description",
  "floors_count": 3,
  "geometry": "POLYGON(...)",
  "created_at": "2026-01-31T12:00:00",
  "updated_at": "2026-01-31T12:00:00"
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid UUID format
- `404`: Building not found

---

#### Get Building Floors
```
GET /api/buildings/{id}/floors
```

**Description:** Get all floors for a specific building.

**Parameters:**
- `id` (path, required): UUID of the building

**Response:**
```json
[
  {
    "id": "uuid",
    "building_id": "uuid",
    "level_number": 1,
    "name": "First Floor",
    "height_meters": 3.5,
    "floor_geojson": {...}
  }
]
```

**Status Codes:**
- `200`: Success
- `400`: Invalid UUID format
- `404`: Building not found

---

### 🗺️ Floor Map APIs

#### Get Floor GeoJSON
```
GET /api/floors/{id}/map
```

**Description:** Retrieve the floor map as a GeoJSON FeatureCollection. This data is directly compatible with Mapbox and other mapping libraries.

**Parameters:**
- `id` (path, required): UUID of the floor

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[...]]
      },
      "properties": {
        "type": "room",
        "name": "Room 101"
      }
    }
  ]
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid UUID format
- `404`: Floor not found

**Usage with Mapbox:**
```javascript
const response = await fetch('/api/floors/{floor_id}/map');
const geojson = await response.json();
map.addSource('floor-plan', {
  type: 'geojson',
  data: geojson
});
```

---

### 🧭 Navigation APIs

#### Calculate Route
```
POST /api/navigation/route
```

**Description:** Calculate the optimal navigation route from a starting coordinate to a destination POI (Point of Interest).

**Request Body:**
```json
{
  "from": {
    "floorId": "uuid",
    "lat": 30.12,
    "lng": 31.45
  },
  "to": {
    "poiId": "uuid"
  },
  "options": {
    "accessible": true
  }
}
```

**Request Fields:**
- `from.floorId` (string, required): UUID of the starting floor
- `from.lat` (float, required): Latitude of starting position
- `from.lng` (float, required): Longitude of starting position
- `to.poiId` (string, required): UUID of destination POI
- `options.accessible` (boolean, optional): Use accessible routes only (default: true)

**Response:**
```json
{
  "floors": [
    {
      "floorId": "uuid",
      "path": [
        [31.45, 30.12],
        [31.46, 30.13],
        [31.47, 30.14]
      ]
    }
  ],
  "distance": 120.5,
  "steps": [
    "Start on floor uuid",
    "Head towards destination",
    "Continue straight for 20.5m",
    "Change to floor uuid",
    "You have arrived at your destination"
  ]
}
```

**Response Fields:**
- `floors`: Array of floor paths
  - `floorId`: UUID of the floor
  - `path`: Array of coordinates [lng, lat] representing the route
- `distance`: Total route distance in meters
- `steps`: Array of human-readable navigation instructions

**Status Codes:**
- `200`: Success - route calculated
- `400`: Invalid UUID format or invalid request
- `404`: POI not found or no route available
- `500`: Route calculation error

**Algorithm:**
The routing engine uses NetworkX to implement Dijkstra's algorithm for finding the shortest path through the building's routing graph. It considers:
- Routing nodes and edges from the database
- Accessibility requirements (elevators, ramps vs stairs)
- Multi-floor navigation with floor transitions
- Real-world distances between nodes

---

## Data Models

### Building
- Contains building metadata and footprint geometry
- Links to multiple floors
- Stores floor count and descriptive information

### Floor
- Belongs to a building
- Contains complete GeoJSON representation of the floor plan
- Includes level number and height information

### POI (Point of Interest)
- Represents destinations (shops, restrooms, elevators, etc.)
- Located on a specific floor
- Has point geometry and metadata

### Routing Graph
- **Routing Nodes**: Waypoints in the navigation graph
- **Routing Edges**: Connections between nodes with distances
- **Node Types**: hallway, door, stairs, elevator
- **Edge Types**: hallway, stairs, elevator, escalator
- Accessibility flags for accessible route planning

---

## Error Handling

All endpoints follow a consistent error response format:

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

Common error scenarios:
- Invalid UUID format → 400 Bad Request
- Resource not found → 404 Not Found
- Route calculation failures → 404 or 500
- Database errors → 500 Internal Server Error

---

## Integration Examples

### Mapbox Integration
```javascript
// Load floor map
const floorMap = await fetch(`/api/floors/${floorId}/map`).then(r => r.json());
map.addSource('floor-plan', { type: 'geojson', data: floorMap });

// Calculate and display route
const route = await fetch('/api/navigation/route', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    from: { floorId, lat, lng },
    to: { poiId },
    options: { accessible: true }
  })
}).then(r => r.json());

// Add route to map
route.floors.forEach(floor => {
  map.addSource(`route-${floor.floorId}`, {
    type: 'geojson',
    data: {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: floor.path
      }
    }
  });
});
```

---

## Technical Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with PostGIS extension
- **ORM**: SQLAlchemy with async support
- **Routing Engine**: NetworkX (Dijkstra's algorithm)
- **Geospatial**: GeoAlchemy2, GEOS

---

## Running the Service

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost/navdb"

# Run the service
python main.py
```

The API will be available at `http://localhost:8000`

API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
