"""Pytest configuration and shared fixtures for navigation service tests."""

import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import networkx as nx

# Set pytest-asyncio mode
pytest_plugins = ["pytest_asyncio"]


# =============================================================================
# GeoJSON Fixtures
# =============================================================================

@pytest.fixture
def simple_corridor_geojson():
    """Simple L-shaped corridor GeoJSON."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [10, 0], [10, 10]]
                },
                "properties": {"space_type": "corridor"}
            }
        ]
    }


@pytest.fixture
def corridor_with_door_geojson():
    """Corridor with a door feature."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [20, 0]]
                },
                "properties": {"space_type": "corridor"}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[10, -2], [10, 0]]
                },
                "properties": {"space_type": "door", "name": "Room 101 Entrance"}
            }
        ]
    }


@pytest.fixture
def corridor_with_room_geojson():
    """Corridor with door and room polygon."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [30, 0]]
                },
                "properties": {"space_type": "corridor"}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[15, -2], [15, 0]]
                },
                "properties": {"space_type": "door", "name": "Room 102 Entrance"}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10, -10], [20, -10], [20, -2], [10, -2], [10, -10]]]
                },
                "properties": {"space_type": "office", "name": "Room 102"}
            }
        ]
    }


@pytest.fixture
def multi_corridor_junction_geojson():
    """Intersecting corridors forming a junction."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-10, 0], [10, 0]]
                },
                "properties": {"space_type": "corridor"}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, -10], [0, 10]]
                },
                "properties": {"space_type": "corridor"}
            }
        ]
    }


@pytest.fixture
def stairs_connector_geojson():
    """Corridor with stairs connector."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [10, 0]]
                },
                "properties": {"space_type": "corridor"}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[10, -2], [10, 2]]
                },
                "properties": {"space_type": "stairs", "name": "Main Stairwell"}
            }
        ]
    }


@pytest.fixture
def empty_geojson():
    """Empty GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": []
    }


@pytest.fixture
def invalid_geojson():
    """Invalid GeoJSON missing required fields."""
    return {
        "type": "FeatureCollection"
        # Missing 'features' key
    }


@pytest.fixture
def non_feature_collection_geojson():
    """GeoJSON that is not a FeatureCollection."""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {}
    }


# =============================================================================
# Mock Model Fixtures
# =============================================================================

@pytest.fixture
def mock_building():
    """Create a mock building model."""
    building = MagicMock()
    building.id = uuid.uuid4()
    building.name = "Test Building"
    building.description = "A test building"
    building.floors_count = 2
    building.created_at = datetime.utcnow()
    building.updated_at = datetime.utcnow()
    return building


@pytest.fixture
def mock_floor(mock_building):
    """Create a mock floor model."""
    floor = MagicMock()
    floor.id = uuid.uuid4()
    floor.building_id = mock_building.id
    floor.level_number = 0
    floor.name = "Ground Floor"
    floor.height_meters = 3.5
    floor.floor_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [10, 0]]},
                "properties": {"space_type": "corridor"}
            }
        ]
    }
    floor.created_at = datetime.utcnow()
    floor.updated_at = datetime.utcnow()
    return floor


@pytest.fixture
def mock_floor_upper(mock_building):
    """Create a mock upper floor for multi-floor testing."""
    floor = MagicMock()
    floor.id = uuid.uuid4()
    floor.building_id = mock_building.id
    floor.level_number = 1
    floor.name = "First Floor"
    floor.height_meters = 3.5
    floor.floor_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [10, 0]]},
                "properties": {"space_type": "corridor"}
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[5, -2], [5, 2]]},
                "properties": {"space_type": "stairs", "name": "Main Stairwell"}
            }
        ]
    }
    return floor


@pytest.fixture
def mock_poi(mock_floor):
    """Create a mock POI model."""
    poi = MagicMock()
    poi.id = uuid.uuid4()
    poi.floor_id = mock_floor.id
    poi.name = "Test Room"
    poi.type = "office"
    poi.geometry = f"POINT(5 0)"  # WKT format
    poi.extra_data = {}
    return poi


@pytest.fixture
def mock_graph_version(mock_building):
    """Create a mock navigation graph version."""
    version = MagicMock()
    version.id = uuid.uuid4()
    version.building_id = mock_building.id
    version.version_number = 1
    version.is_active = True
    version.created_at = datetime.utcnow()
    return version


@pytest.fixture
def mock_node_type():
    """Create a mock node type."""
    node_type = MagicMock()
    node_type.id = uuid.uuid4()
    node_type.code = "corridor"
    node_type.description = "Corridor node"
    return node_type


@pytest.fixture
def mock_edge_type():
    """Create a mock edge type."""
    edge_type = MagicMock()
    edge_type.id = uuid.uuid4()
    edge_type.code = "corridor"
    edge_type.is_accessible = True
    edge_type.description = "Corridor edge"
    return edge_type


# =============================================================================
# Async Database Session Fixture
# =============================================================================

@pytest.fixture
async def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    return session


# =============================================================================
# NetworkX Graph Fixtures
# =============================================================================

@pytest.fixture
def simple_connected_graph():
    """Create a simple connected graph for testing."""
    G = nx.Graph()
    # Add nodes with floor_id and coordinates
    G.add_node("node1", floor_id="floor1", lat=0.0, lng=0.0, node_type_id="type1")
    G.add_node("node2", floor_id="floor1", lat=0.0, lng=10.0, node_type_id="type1")
    G.add_node("node3", floor_id="floor1", lat=0.0, lng=20.0, node_type_id="type1")
    # Add edges with weights
    G.add_edge("node1", "node2", weight=10.0, edge_type_id="edge_type1")
    G.add_edge("node2", "node3", weight=10.0, edge_type_id="edge_type1")
    return G


@pytest.fixture
def disconnected_graph():
    """Create a disconnected graph (two components)."""
    G = nx.Graph()
    # Component 1
    G.add_node("node1", floor_id="floor1", lat=0.0, lng=0.0)
    G.add_node("node2", floor_id="floor1", lat=0.0, lng=10.0)
    G.add_edge("node1", "node2", weight=10.0)
    # Component 2 (disconnected)
    G.add_node("node3", floor_id="floor1", lat=100.0, lng=100.0)
    G.add_node("node4", floor_id="floor1", lat=100.0, lng=110.0)
    G.add_edge("node3", "node4", weight=10.0)
    return G


@pytest.fixture
def multi_floor_graph():
    """Create a graph spanning multiple floors."""
    G = nx.Graph()
    # Floor 1 nodes
    G.add_node("f1_node1", floor_id="floor1", lat=0.0, lng=0.0)
    G.add_node("f1_node2", floor_id="floor1", lat=0.0, lng=10.0)
    G.add_node("f1_stairs", floor_id="floor1", lat=5.0, lng=5.0)
    G.add_edge("f1_node1", "f1_node2", weight=10.0)
    G.add_edge("f1_node2", "f1_stairs", weight=5.0)
    # Floor 2 nodes
    G.add_node("f2_node1", floor_id="floor2", lat=0.0, lng=0.0)
    G.add_node("f2_node2", floor_id="floor2", lat=0.0, lng=10.0)
    G.add_node("f2_stairs", floor_id="floor2", lat=5.0, lng=5.0)
    G.add_edge("f2_node1", "f2_node2", weight=10.0)
    G.add_edge("f2_node2", "f2_stairs", weight=5.0)
    # Vertical connector (stairs)
    G.add_edge("f1_stairs", "f2_stairs", weight=3.0, edge_type_id="vertical")
    return G


@pytest.fixture
def graph_with_self_loops():
    """Graph with self-loops for cleanup testing."""
    G = nx.Graph()
    G.add_node("node1", floor_id="floor1", lat=0.0, lng=0.0)
    G.add_node("node2", floor_id="floor1", lat=0.0, lng=10.0)
    G.add_edge("node1", "node2", weight=10.0)
    G.add_edge("node1", "node1", weight=0.0)  # Self-loop
    return G


@pytest.fixture
def graph_with_zero_edges():
    """Graph with zero-length edges for cleanup testing."""
    G = nx.Graph()
    G.add_node("node1", floor_id="floor1", lat=0.0, lng=0.0)
    G.add_node("node2", floor_id="floor1", lat=0.0, lng=10.0)
    G.add_edge("node1", "node2", weight=0.0)  # Zero weight
    return G


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def valid_route_request():
    """Valid route request payload."""
    return {
        "from": {
            "floorId": str(uuid.uuid4()),
            "lat": 30.04,
            "lng": 31.23
        },
        "to": {
            "poiId": str(uuid.uuid4())
        },
        "options": {
            "accessible": True
        }
    }


@pytest.fixture
def invalid_route_request_missing_field():
    """Route request with missing required field."""
    return {
        "from": {
            "floorId": str(uuid.uuid4()),
            "lat": 30.04
            # Missing lng
        },
        "to": {
            "poiId": str(uuid.uuid4())
        }
    }


@pytest.fixture
def invalid_route_request_bad_uuid():
    """Route request with invalid UUID format."""
    return {
        "from": {
            "floorId": "not-a-uuid",
            "lat": 30.04,
            "lng": 31.23
        },
        "to": {
            "poiId": str(uuid.uuid4())
        }
    }
