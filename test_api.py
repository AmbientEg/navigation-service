"""
Test file to verify API endpoints are properly configured.
Run this after starting the server to test the endpoints.
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health Check: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    return response.status_code == 200


def test_get_building(building_id: str):
    """Test getting a building by ID"""
    response = requests.get(f"{BASE_URL}/api/buildings/{building_id}")
    print(f"\nGet Building: {response.status_code}")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(response.json())
    return response.status_code


def test_get_building_floors(building_id: str):
    """Test getting floors for a building"""
    response = requests.get(f"{BASE_URL}/api/buildings/{building_id}/floors")
    print(f"\nGet Building Floors: {response.status_code}")
    if response.status_code == 200:
        print(f"Found {len(response.json())} floors")
        print(json.dumps(response.json(), indent=2))
    else:
        print(response.json())
    return response.status_code


def test_get_floor_map(floor_id: str):
    """Test getting floor map GeoJSON"""
    response = requests.get(f"{BASE_URL}/api/floors/{floor_id}/map")
    print(f"\nGet Floor Map: {response.status_code}")
    if response.status_code == 200:
        geojson = response.json()
        print(f"Type: {geojson.get('type')}")
        print(f"Features: {len(geojson.get('features', []))}")
    else:
        print(response.json())
    return response.status_code


def test_calculate_route():
    """Test route calculation"""
    route_request = {
        "from": {
            "floorId": "123e4567-e89b-12d3-a456-426614174000",
            "lat": 30.12,
            "lng": 31.45
        },
        "to": {
            "poiId": "123e4567-e89b-12d3-a456-426614174001"
        },
        "options": {
            "accessible": True
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/navigation/route",
        json=route_request,
        headers={"Content-Type": "application/json"}
    )
    print(f"\nCalculate Route: {response.status_code}")
    if response.status_code == 200:
        route = response.json()
        print(f"Distance: {route['distance']}m")
        print(f"Floors: {len(route['floors'])}")
        print(f"Steps: {len(route['steps'])}")
        print(json.dumps(route, indent=2))
    else:
        print(response.json())
    return response.status_code


def test_docs():
    """Test that API documentation is accessible"""
    response = requests.get(f"{BASE_URL}/docs")
    print(f"\nAPI Documentation: {response.status_code}")
    return response.status_code == 200


if __name__ == "__main__":
    print("=" * 60)
    print("Navigation Service API Tests")
    print("=" * 60)
    
    print("\n🔍 Testing API Endpoints...")
    
    # Test health
    if test_health():
        print("✅ Health check passed")
    else:
        print("❌ Health check failed")
    
    # Test docs
    if test_docs():
        print("✅ API documentation accessible")
    else:
        print("❌ API documentation not accessible")
    
    print("\n" + "=" * 60)
    print("Note: Building, Floor, and Navigation tests require")
    print("valid UUIDs from your database. Update the test")
    print("functions with real IDs to test those endpoints.")
    print("=" * 60)
    
    # Example tests with placeholder UUIDs (will fail without data)
    print("\n📝 Example endpoint tests (will fail without data):")
    test_get_building("123e4567-e89b-12d3-a456-426614174000")
    test_get_building_floors("123e4567-e89b-12d3-a456-426614174000")
    test_get_floor_map("123e4567-e89b-12d3-a456-426614174000")
    test_calculate_route()
