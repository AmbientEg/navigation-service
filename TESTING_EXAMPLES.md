# API Testing Examples

This file contains example curl commands and requests for testing the Navigation Service API.

## Health Check

```bash
curl -X GET http://localhost:8000/health
```

## Building APIs

### Get Building by ID
```bash
curl -X GET http://localhost:8000/api/buildings/{building-uuid}
```

Example with UUID:
```bash
curl -X GET http://localhost:8000/api/buildings/123e4567-e89b-12d3-a456-426614174000
```

### Get Building Floors
```bash
curl -X GET http://localhost:8000/api/buildings/{building-uuid}/floors
```

Example:
```bash
curl -X GET http://localhost:8000/api/buildings/123e4567-e89b-12d3-a456-426614174000/floors
```

## Floor APIs

### Get Floor Map (GeoJSON)
```bash
curl -X GET http://localhost:8000/api/floors/{floor-uuid}/map
```

Example:
```bash
curl -X GET http://localhost:8000/api/floors/123e4567-e89b-12d3-a456-426614174001/map
```

### Pretty print JSON response
```bash
curl -X GET http://localhost:8000/api/floors/{floor-uuid}/map | python -m json.tool
```

## Navigation APIs

### Calculate Route
```bash
curl -X POST http://localhost:8000/api/navigation/route \
  -H "Content-Type: application/json" \
  -d '{
    "from": {
      "floorId": "123e4567-e89b-12d3-a456-426614174000",
      "lat": 30.12,
      "lng": 31.45
    },
    "to": {
      "poiId": "123e4567-e89b-12d3-a456-426614174001"
    },
    "options": {
      "accessible": true
    }
  }'
```

### Calculate Route (Non-Accessible)
```bash
curl -X POST http://localhost:8000/api/navigation/route \
  -H "Content-Type: application/json" \
  -d '{
    "from": {
      "floorId": "floor-uuid",
      "lat": 30.12,
      "lng": 31.45
    },
    "to": {
      "poiId": "poi-uuid"
    },
    "options": {
      "accessible": false
    }
  }'
```

### Pretty print route response
```bash
curl -X POST http://localhost:8000/api/navigation/route \
  -H "Content-Type: application/json" \
  -d '{...}' | python -m json.tool
```

## Using Python Requests

### Installation
```bash
pip install requests
```

### Get Building
```python
import requests

building_id = "123e4567-e89b-12d3-a456-426614174000"
response = requests.get(f"http://localhost:8000/api/buildings/{building_id}")
print(response.json())
```

### Get Floor Map
```python
import requests

floor_id = "123e4567-e89b-12d3-a456-426614174001"
response = requests.get(f"http://localhost:8000/api/floors/{floor_id}/map")
geojson = response.json()
print(f"Type: {geojson['type']}")
print(f"Features: {len(geojson['features'])}")
```

### Calculate Route
```python
import requests

route_request = {
    "from": {
        "floorId": "floor-uuid",
        "lat": 30.12,
        "lng": 31.45
    },
    "to": {
        "poiId": "poi-uuid"
    },
    "options": {
        "accessible": True
    }
}

response = requests.post(
    "http://localhost:8000/api/navigation/route",
    json=route_request
)
route = response.json()
print(f"Distance: {route['distance']}m")
print(f"Steps: {route['steps']}")
```

## Using JavaScript Fetch

### Get Building
```javascript
const buildingId = '123e4567-e89b-12d3-a456-426614174000';

fetch(`http://localhost:8000/api/buildings/${buildingId}`)
  .then(response => response.json())
  .then(building => console.log(building))
  .catch(error => console.error('Error:', error));
```

### Get Floor Map for Mapbox
```javascript
const floorId = '123e4567-e89b-12d3-a456-426614174001';

fetch(`http://localhost:8000/api/floors/${floorId}/map`)
  .then(response => response.json())
  .then(geojson => {
    // Add to Mapbox map
    map.addSource('floor-plan', {
      type: 'geojson',
      data: geojson
    });
    
    map.addLayer({
      id: 'floor-plan-layer',
      type: 'fill',
      source: 'floor-plan',
      paint: {
        'fill-color': '#888888',
        'fill-opacity': 0.4
      }
    });
  });
```

### Calculate and Display Route
```javascript
const routeRequest = {
  from: {
    floorId: 'floor-uuid',
    lat: 30.12,
    lng: 31.45
  },
  to: {
    poiId: 'poi-uuid'
  },
  options: {
    accessible: true
  }
};

fetch('http://localhost:8000/api/navigation/route', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(routeRequest)
})
  .then(response => response.json())
  .then(route => {
    console.log(`Distance: ${route.distance}m`);
    console.log('Steps:', route.steps);
    
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
      
      map.addLayer({
        id: `route-${floor.floorId}`,
        type: 'line',
        source: `route-${floor.floorId}`,
        paint: {
          'line-color': '#007cbf',
          'line-width': 4
        }
      });
    });
  });
```

## Error Handling Examples

### Handle 404 Not Found
```bash
curl -v -X GET http://localhost:8000/api/buildings/invalid-uuid
```

Response:
```json
{
  "detail": "Invalid building ID format"
}
```

### Handle Invalid Route
```bash
curl -X POST http://localhost:8000/api/navigation/route \
  -H "Content-Type: application/json" \
  -d '{
    "from": {
      "floorId": "nonexistent",
      "lat": 30.12,
      "lng": 31.45
    },
    "to": {
      "poiId": "nonexistent"
    },
    "options": {
      "accessible": true
    }
  }'
```

## Batch Requests Example

### Get Multiple Buildings
```python
import requests
import asyncio
import aiohttp

async def get_building(session, building_id):
    async with session.get(f'http://localhost:8000/api/buildings/{building_id}') as resp:
        return await resp.json()

async def main():
    building_ids = [
        '123e4567-e89b-12d3-a456-426614174000',
        '123e4567-e89b-12d3-a456-426614174001',
        '123e4567-e89b-12d3-a456-426614174002'
    ]
    
    async with aiohttp.ClientSession() as session:
        tasks = [get_building(session, bid) for bid in building_ids]
        buildings = await asyncio.gather(*tasks)
        for building in buildings:
            print(building)

asyncio.run(main())
```

## Testing Checklist

- [ ] Health endpoint responds
- [ ] API documentation accessible at /docs
- [ ] Get building by valid UUID
- [ ] Get building with invalid UUID returns 400
- [ ] Get building with non-existent UUID returns 404
- [ ] Get building floors returns array
- [ ] Get floor map returns GeoJSON FeatureCollection
- [ ] Calculate route with valid data
- [ ] Calculate route with accessible option
- [ ] Calculate route with invalid UUIDs returns 400
- [ ] Calculate route with non-existent POI returns 404

## Notes

- Replace UUIDs in examples with actual UUIDs from your database
- Ensure the server is running before testing
- Check server logs for detailed error messages
- Use `/docs` endpoint for interactive API testing
