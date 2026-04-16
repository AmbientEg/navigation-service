"""Integration tests for the navigation API endpoints."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from main import app


# =============================================================================
# Navigation Route Endpoint Tests
# =============================================================================

class TestNavigationRoute:
    """Tests for POST /api/navigation/route endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_route_success(self, client, valid_route_request, mock_db_session):
        """Should calculate route successfully with valid request."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.return_value = {
                    "buildingId": str(uuid.uuid4()),
                    "floors": [{"floorId": str(uuid.uuid4()), "path": [[31.23, 30.04], [31.24, 30.05]]}],
                    "distance": 150.5,
                    "steps": ["Start here", "Walk 100m", "You have arrived"]
                }

                response = client.post("/api/navigation/route", json=valid_route_request)

                assert response.status_code == 200
                data = response.json()
                assert "buildingId" in data
                assert "floors" in data
                assert "distance" in data
                assert "steps" in data

    def test_route_invalid_uuid_format(self, client, invalid_route_request_bad_uuid):
        """Should return 400 for invalid UUID format."""
        response = client.post("/api/navigation/route", json=invalid_route_request_bad_uuid)

        assert response.status_code == 400
        assert "Invalid UUID" in response.json()["detail"]

    def test_route_poi_not_found(self, client, valid_route_request, mock_db_session):
        """Should return 404 when destination POI not found."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.side_effect = ValueError("POI not found")

                response = client.post("/api/navigation/route", json=valid_route_request)

                assert response.status_code == 404
                assert "POI not found" in response.json()["detail"]

    def test_route_no_active_graph(self, client, valid_route_request, mock_db_session):
        """Should return 404 when no active graph version."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.side_effect = ValueError("No active navigation graph version")

                response = client.post("/api/navigation/route", json=valid_route_request)

                assert response.status_code == 404

    def test_route_no_path_found(self, client, valid_route_request, mock_db_session):
        """Should return 404 when no path exists between points."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.side_effect = ValueError("No route found")

                response = client.post("/api/navigation/route", json=valid_route_request)

                assert response.status_code == 404

    def test_route_internal_error(self, client, valid_route_request, mock_db_session):
        """Should return 500 on unexpected error."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.side_effect = Exception("Unexpected error")

                response = client.post("/api/navigation/route", json=valid_route_request)

                assert response.status_code == 500
                assert "Route calculation failed" in response.json()["detail"]

    def test_route_missing_required_field(self, client):
        """Should return 422 when required field is missing."""
        invalid_request = {
            "from": {
                "floorId": str(uuid.uuid4()),
                "lat": 30.04
                # Missing lng
            },
            "to": {
                "poiId": str(uuid.uuid4())
            }
        }

        response = client.post("/api/navigation/route", json=invalid_request)

        assert response.status_code == 422

    def test_route_invalid_types(self, client):
        """Should return 422 when fields have wrong types."""
        invalid_request = {
            "from": {
                "floorId": str(uuid.uuid4()),
                "lat": "not a number",  # Should be float
                "lng": 31.23
            },
            "to": {
                "poiId": str(uuid.uuid4())
            }
        }

        response = client.post("/api/navigation/route", json=invalid_request)

        assert response.status_code == 422

    def test_route_cross_building(self, client, valid_route_request, mock_db_session):
        """Should return 404 for cross-building routes."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.side_effect = ValueError("Cross-building routing is not supported")

                response = client.post("/api/navigation/route", json=valid_route_request)

                assert response.status_code == 404

    def test_route_accessible_option(self, client, mock_db_session):
        """Should respect accessible routing option."""
        request_with_accessible = {
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

        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.return_value = {
                    "buildingId": str(uuid.uuid4()),
                    "floors": [],
                    "distance": 100.0,
                    "steps": ["Start", "Arrive"]
                }

                response = client.post("/api/navigation/route", json=request_with_accessible)

                assert response.status_code == 200
                # Verify accessible flag was passed
                call_kwargs = mock_calc.call_args[1]
                assert call_kwargs.get('accessible') == True

    def test_route_empty_steps_for_arrival(self, client, mock_db_session):
        """Should handle arrival at destination edge case."""
        request = {
            "from": {
                "floorId": str(uuid.uuid4()),
                "lat": 30.04,
                "lng": 31.23
            },
            "to": {
                "poiId": str(uuid.uuid4())
            }
        }

        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.navigation_routes.routing_service.calculate_route') as mock_calc:
                mock_calc.return_value = {
                    "buildingId": str(uuid.uuid4()),
                    "floors": [{"floorId": str(uuid.uuid4()), "path": [[31.23, 30.04]]}],
                    "distance": 0.0,
                    "steps": ["You have arrived at your destination"]
                }

                response = client.post("/api/navigation/route", json=request)

                assert response.status_code == 200
                assert response.json()["distance"] == 0.0


# =============================================================================
# Route Response Model Validation Tests
# =============================================================================

class TestRouteResponseValidation:
    """Tests for response model validation."""

    def test_valid_route_response_structure(self):
        """Should validate correct response structure."""
        from routes.navigation_routes import RouteResponse, RouteFloorPath

        floor_path = RouteFloorPath(floorId=str(uuid.uuid4()), path=[[31.23, 30.04], [31.24, 30.05]])
        response = RouteResponse(
            buildingId=str(uuid.uuid4()),
            floors=[floor_path],
            distance=150.5,
            steps=["Step 1", "Step 2"]
        )

        assert response.floors[0].floorId is not None
        assert response.distance > 0
        assert len(response.steps) > 0

    def test_empty_path_response(self):
        """Should handle empty path in response."""
        from routes.navigation_routes import RouteResponse

        response = RouteResponse(
            buildingId=str(uuid.uuid4()),
            floors=[],
            distance=0.0,
            steps=["You have arrived"]
        )

        assert response.floors == []
        assert response.distance == 0.0


# =============================================================================
# Route Request Model Validation Tests
# =============================================================================

class TestRouteRequestValidation:
    """Tests for request model validation."""

    def test_valid_route_request(self):
        """Should validate correct request structure."""
        from routes.navigation_routes import RouteRequest, RouteFrom, RouteTo

        route_from = RouteFrom(floorId=str(uuid.uuid4()), lat=30.04, lng=31.23)
        route_to = RouteTo(poiId=str(uuid.uuid4()))
        request = RouteRequest(from_=route_from, to=route_to)

        assert request.from_.lat == 30.04
        assert request.to.poiId is not None

    def test_route_request_with_default_options(self):
        """Should use default options when not provided."""
        from routes.navigation_routes import RouteRequest, RouteFrom, RouteTo

        route_from = RouteFrom(floorId=str(uuid.uuid4()), lat=30.04, lng=31.23)
        route_to = RouteTo(poiId=str(uuid.uuid4()))
        request = RouteRequest(from_=route_from, to=route_to)

        assert request.options.accessible == True  # Default value

    def test_route_request_alias_handling(self):
        """Should handle 'from' field alias correctly."""
        from routes.navigation_routes import RouteRequest

        # Using the alias "from" instead of "from_"
        request = RouteRequest.model_validate({
            "from": {
                "floorId": str(uuid.uuid4()),
                "lat": 30.04,
                "lng": 31.23
            },
            "to": {
                "poiId": str(uuid.uuid4())
            }
        })

        assert request.from_.lat == 30.04

    def test_invalid_coordinates(self):
        """Should reject invalid coordinate values."""
        from routes.navigation_routes import RouteFrom
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RouteFrom(floorId=str(uuid.uuid4()), lat=200.0, lng=31.23)  # Invalid latitude

    def test_negative_coordinates(self):
        """Should accept negative coordinates (southern/western hemisphere)."""
        from routes.navigation_routes import RouteFrom

        route_from = RouteFrom(floorId=str(uuid.uuid4()), lat=-30.04, lng=-31.23)

        assert route_from.lat == -30.04
        assert route_from.lng == -31.23
