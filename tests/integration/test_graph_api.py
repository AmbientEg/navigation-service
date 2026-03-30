"""Integration tests for the graph workflow API endpoints."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from main import app


class TestGraphRebuild:
    """Tests for POST /api/graphs/rebuild/{building_id} endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_rebuild_success(self, client, mock_db_session, mock_building):
        """Should successfully rebuild graph preview."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {
                    "building_id": str(mock_building.id),
                    "nodes": [{"id": "n1", "floor_id": str(uuid.uuid4())}],
                    "edges": [{"id": "e1", "from": "n1", "to": "n2"}],
                    "summary": {"total_nodes": 1, "total_edges": 1, "floors_processed": 1}
                }

                response = client.post(f"/api/graphs/rebuild/{mock_building.id}")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "preview"
                assert "nodes" in data
                assert "edges" in data
                assert "summary" in data

    def test_rebuild_invalid_building_id(self, client):
        """Should return 400 for invalid building ID format."""
        response = client.post("/api/graphs/rebuild/not-a-uuid")

        assert response.status_code == 400
        assert "Invalid building ID" in response.json()["detail"]

    def test_rebuild_building_not_found(self, client, mock_db_session):
        """Should return 404 when building not found."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.side_effect = ValueError("Building not found")

                response = client.post(f"/api/graphs/rebuild/{uuid.uuid4()}")

                assert response.status_code == 404

    def test_rebuild_no_floors(self, client, mock_db_session):
        """Should return 404 when building has no floors."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.side_effect = ValueError("No floors found")

                response = client.post(f"/api/graphs/rebuild/{uuid.uuid4()}")

                assert response.status_code == 404

    def test_rebuild_internal_error(self, client, mock_db_session):
        """Should return 500 on unexpected error."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.side_effect = Exception("Database connection failed")

                response = client.post(f"/api/graphs/rebuild/{uuid.uuid4()}")

                assert response.status_code == 500

    def test_rebuild_multi_floor_preview(self, client, mock_db_session):
        """Should return preview with multiple floors."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {
                    "building_id": str(uuid.uuid4()),
                    "nodes": [
                        {"id": "f0_n1", "floor_id": str(uuid.uuid4()), "floor_level": 0},
                        {"id": "f1_n1", "floor_id": str(uuid.uuid4()), "floor_level": 1}
                    ],
                    "edges": [
                        {"id": "f0_e1", "from": "f0_n1", "to": "f0_n2"},
                        {"id": "stitch_e1", "from": "f0_n1", "to": "f1_n1", "is_stitched": True}
                    ],
                    "summary": {
                        "total_nodes": 2,
                        "total_edges": 2,
                        "stitched_edges": 1,
                        "floors_processed": 2
                    }
                }

                response = client.post(f"/api/graphs/rebuild/{uuid.uuid4()}")

                assert response.status_code == 200
                assert response.json()["summary"]["floors_processed"] == 2
                assert response.json()["summary"]["stitched_edges"] == 1


class TestGraphConfirm:
    """Tests for POST /api/graphs/confirm/{building_id} endpoint."""

    def test_confirm_success(self, client, mock_db_session, mock_building):
        """Should confirm and persist graph version."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {
                    "building_id": str(mock_building.id),
                    "nodes": [{"id": "n1"}],
                    "edges": [],
                    "summary": {"total_nodes": 1, "total_edges": 0}
                }

                with patch('routes.graph_routes.confirm_graph_preview') as mock_confirm:
                    mock_confirm.return_value = {
                        "graph_version_id": str(uuid.uuid4()),
                        "version_number": 2,
                        "persisted": {"nodes": 1, "edges": 0, "floors": 1}
                    }

                    response = client.post(f"/api/graphs/confirm/{mock_building.id}")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "confirmed"
                    assert "graph_version_id" in data
                    assert data["persisted"]["nodes"] == 1

    def test_confirm_invalid_building_id(self, client):
        """Should return 400 for invalid building ID."""
        response = client.post("/api/graphs/confirm/not-a-uuid")

        assert response.status_code == 400

    def test_confirm_building_not_found(self, client, mock_db_session):
        """Should return 404 when building not found during preview."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.side_effect = ValueError("Building not found")

                response = client.post(f"/api/graphs/confirm/{uuid.uuid4()}")

                assert response.status_code == 404

    def test_confirm_persistence_error(self, client, mock_db_session):
        """Should return 500 when persistence fails."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {"nodes": [], "edges": [], "summary": {}}

                with patch('routes.graph_routes.confirm_graph_preview') as mock_confirm:
                    mock_confirm.side_effect = Exception("Database error")

                    response = client.post(f"/api/graphs/confirm/{uuid.uuid4()}")

                    assert response.status_code == 500

    def test_confirm_version_activation(self, client, mock_db_session):
        """Should create new version and activate it."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {
                    "nodes": [{"id": "n1", "floor_id": str(uuid.uuid4())}],
                    "edges": [],
                    "summary": {"floors_processed": 1}
                }

                with patch('routes.graph_routes.confirm_graph_preview') as mock_confirm:
                    mock_confirm.return_value = {
                        "graph_version_id": str(uuid.uuid4()),
                        "version_number": 3,
                        "previous_active_version_id": str(uuid.uuid4()),
                        "persisted": {"nodes": 100, "edges": 200}
                    }

                    response = client.post(f"/api/graphs/confirm/{uuid.uuid4()}")

                    assert response.status_code == 200
                    assert response.json()["version_number"] == 3
                    assert "previous_active_version_id" in response.json()


class TestGraphRollback:
    """Tests for POST /api/graphs/rollback/{building_id} endpoint."""

    def test_rollback_success(self, client, mock_db_session):
        """Should rollback to previous version successfully."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.rollback_to_previous_graph_version') as mock_rollback:
                mock_rollback.return_value = {
                    "rolled_back_to_version_id": str(uuid.uuid4()),
                    "rolled_back_to_version_number": 1,
                    "previous_active_version_id": str(uuid.uuid4()),
                    "previous_active_version_number": 2
                }

                response = client.post(f"/api/graphs/rollback/{uuid.uuid4()}")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "rolled_back"
                assert data["rolled_back_to_version_number"] == 1

    def test_rollback_invalid_building_id(self, client):
        """Should return 400 for invalid building ID."""
        response = client.post("/api/graphs/rollback/not-a-uuid")

        assert response.status_code == 400

    def test_rollback_no_previous_version(self, client, mock_db_session):
        """Should return 404 when no previous version exists."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.rollback_to_previous_graph_version') as mock_rollback:
                mock_rollback.side_effect = ValueError("No previous graph version")

                response = client.post(f"/api/graphs/rollback/{uuid.uuid4()}")

                assert response.status_code == 404

    def test_rollback_no_active_version(self, client, mock_db_session):
        """Should return 404 when no active version exists."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.rollback_to_previous_graph_version') as mock_rollback:
                mock_rollback.side_effect = ValueError("No active graph version found")

                response = client.post(f"/api/graphs/rollback/{uuid.uuid4()}")

                assert response.status_code == 404

    def test_rollback_internal_error(self, client, mock_db_session):
        """Should return 500 on unexpected error."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.rollback_to_previous_graph_version') as mock_rollback:
                mock_rollback.side_effect = Exception("Database error")

                response = client.post(f"/api/graphs/rollback/{uuid.uuid4()}")

                assert response.status_code == 500


class TestGraphWorkflowEdgeCases:
    """Edge case tests for graph workflow."""

    def test_rebuild_empty_building(self, client, mock_db_session):
        """Should handle building with empty floors."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {
                    "building_id": str(uuid.uuid4()),
                    "nodes": [],
                    "edges": [],
                    "summary": {"total_nodes": 0, "total_edges": 0, "floors_processed": 1}
                }

                response = client.post(f"/api/graphs/rebuild/{uuid.uuid4()}")

                assert response.status_code == 200
                assert response.json()["summary"]["total_nodes"] == 0

    def test_confirm_empty_preview(self, client, mock_db_session):
        """Should handle confirming empty graph preview."""
        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {
                    "nodes": [],
                    "edges": [],
                    "summary": {"floors_processed": 1}
                }

                with patch('routes.graph_routes.confirm_graph_preview') as mock_confirm:
                    mock_confirm.return_value = {
                        "graph_version_id": str(uuid.uuid4()),
                        "version_number": 1,
                        "persisted": {"nodes": 0, "edges": 0, "floors": 1}
                    }

                    response = client.post(f"/api/graphs/confirm/{uuid.uuid4()}")

                    assert response.status_code == 200

    def test_concurrent_rebuild_calls(self, client, mock_db_session):
        """Should handle concurrent rebuild requests."""
        building_id = str(uuid.uuid4())

        with patch('database.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('routes.graph_routes.build_graph_preview_for_building') as mock_build:
                mock_build.return_value = {
                    "building_id": building_id,
                    "nodes": [{"id": "n1"}],
                    "edges": [],
                    "summary": {"total_nodes": 1}
                }

                # Simulate concurrent calls
                response1 = client.post(f"/api/graphs/rebuild/{building_id}")
                response2 = client.post(f"/api/graphs/rebuild/{building_id}")

                assert response1.status_code == 200
                assert response2.status_code == 200
