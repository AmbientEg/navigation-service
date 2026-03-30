"""Unit tests for the graph workflow service."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import networkx as nx

from services import graph_workflow_service


class TestSafeName:
    """Tests for _safe_name helper function."""

    def test_safe_name_with_value(self):
        """Should normalize valid name."""
        result = graph_workflow_service._safe_name("  Stairs  ")
        assert result == "stairs"

    def test_safe_name_empty(self):
        """Should return None for empty string."""
        result = graph_workflow_service._safe_name("")
        assert result is None

    def test_safe_name_whitespace(self):
        """Should return None for whitespace-only string."""
        result = graph_workflow_service._safe_name("   ")
        assert result is None

    def test_safe_name_none(self):
        """Should return None for None input."""
        result = graph_workflow_service._safe_name(None)
        assert result is None


class TestDistanceMeters:
    """Tests for _distance_meters helper function."""

    def test_distance_same_point(self):
        """Distance from point to itself should be zero."""
        dist = graph_workflow_service._distance_meters(0, 0, 0, 0)
        assert dist == 0

    def test_distance_known_points(self):
        """Distance calculation should be reasonable."""
        # Approximate distance between (0,0) and (0.001, 0) in degrees
        dist = graph_workflow_service._distance_meters(0, 0, 0.001, 0)
        # Should be approximately 111 meters at equator
        assert 50 < dist < 200

    def test_distance_symmetric(self):
        """Distance should be symmetric."""
        dist1 = graph_workflow_service._distance_meters(0, 0, 1, 1)
        dist2 = graph_workflow_service._distance_meters(1, 1, 0, 0)
        assert dist1 == dist2


class TestExtractCoordinates:
    """Tests for _extract_coordinates helper function."""

    def test_extract_from_tuple(self):
        """Should extract from tuple node."""
        result = graph_workflow_service._extract_coordinates((1.5, 2.5), {})
        assert result == (1.5, 2.5)

    def test_extract_from_list(self):
        """Should extract from list node."""
        result = graph_workflow_service._extract_coordinates([1.5, 2.5], {})
        assert result == (1.5, 2.5)

    def test_extract_from_attrs(self):
        """Should extract from attributes."""
        result = graph_workflow_service._extract_coordinates(None, {"x": 1.5, "y": 2.5})
        assert result == (1.5, 2.5)

    def test_extract_none(self):
        """Should return None for unresolvable coordinates."""
        result = graph_workflow_service._extract_coordinates(None, {})
        assert result is None


class TestIsVerticalCandidate:
    """Tests for _is_vertical_candidate helper function."""

    def test_is_vertical_stairs(self):
        """Stairs should be vertical candidate."""
        node = {"node_type": "stairs", "name": "Main"}
        assert graph_workflow_service._is_vertical_candidate(node) is True

    def test_is_vertical_elevator(self):
        """Elevator should be vertical candidate."""
        node = {"node_type": "elevator", "name": "Lift"}
        assert graph_workflow_service._is_vertical_candidate(node) is True

    def test_is_vertical_by_name(self):
        """Should detect vertical by name hints."""
        node = {"node_type": "corridor", "name": "Stairwell A"}
        assert graph_workflow_service._is_vertical_candidate(node) is True

    def test_not_vertical(self):
        """Regular corridor should not be vertical candidate."""
        node = {"node_type": "corridor", "name": "Hallway"}
        assert graph_workflow_service._is_vertical_candidate(node) is False


class TestPreviewNodesEdges:
    """Tests for _preview_nodes_edges_for_floor function."""

    def test_preview_simple_graph(self, mock_floor):
        """Should generate preview nodes and edges from graph."""
        G = nx.Graph()
        G.add_node((0.0, 0.0), type="corridor")
        G.add_node((10.0, 0.0), type="corridor")
        G.add_edge((0.0, 0.0), (10.0, 0.0), weight=10.0, edge_type="corridor")

        nodes, edges = graph_workflow_service._preview_nodes_edges_for_floor(mock_floor, G)

        assert len(nodes) == 2
        assert len(edges) == 1
        assert all("floor_id" in n for n in nodes)
        assert all("id" in n for n in nodes)

    def test_preview_with_door(self, mock_floor):
        """Should handle door nodes."""
        G = nx.Graph()
        G.add_node((0.0, 0.0), type="corridor")
        G.add_node((10.0, 0.0), type="door", name="Entrance")
        G.add_edge((0.0, 0.0), (10.0, 0.0), weight=10.0, edge_type="corridor")

        nodes, edges = graph_workflow_service._preview_nodes_edges_for_floor(mock_floor, G)

        door_nodes = [n for n in nodes if n["node_type"] == "door"]
        assert len(door_nodes) == 1
        assert door_nodes[0]["name"] == "Entrance"

    def test_preview_empty_graph(self, mock_floor):
        """Should handle empty graph."""
        G = nx.Graph()
        nodes, edges = graph_workflow_service._preview_nodes_edges_for_floor(mock_floor, G)

        assert len(nodes) == 0
        assert len(edges) == 0


class TestStitchAdjacentFloors:
    """Tests for _stitch_adjacent_floors function."""

    def test_stitch_by_name_match(self, mock_floor, mock_floor_upper):
        """Should stitch floors by matching vertical node names."""
        floor_nodes = {
            str(mock_floor.id): [
                {"id": "n1", "lng": 0.0, "lat": 0.0, "node_type": "stairs", "name": "Main Stairwell", "floor_id": str(mock_floor.id)}
            ],
            str(mock_floor_upper.id): [
                {"id": "n2", "lng": 0.0, "lat": 0.0, "node_type": "stairs", "name": "Main Stairwell", "floor_id": str(mock_floor_upper.id)}
            ]
        }

        stitched = graph_workflow_service._stitch_adjacent_floors([mock_floor, mock_floor_upper], floor_nodes)

        assert len(stitched) == 1
        assert stitched[0]["edge_type"] == "vertical_connector"
        assert stitched[0]["is_stitched"] is True

    def test_stitch_fallback_to_nearest(self, mock_floor, mock_floor_upper):
        """Should fallback to nearest nodes if no name match."""
        mock_floor_upper.level_number = 1

        floor_nodes = {
            str(mock_floor.id): [
                {"id": "n1", "lng": 0.0, "lat": 0.0, "node_type": "corridor", "name": "Hallway", "floor_id": str(mock_floor.id)}
            ],
            str(mock_floor_upper.id): [
                {"id": "n2", "lng": 0.001, "lat": 0.0, "node_type": "corridor", "name": "Upper Hallway", "floor_id": str(mock_floor_upper.id)}
            ]
        }

        stitched = graph_workflow_service._stitch_adjacent_floors([mock_floor, mock_floor_upper], floor_nodes)

        assert len(stitched) >= 1

    def test_stitch_single_floor(self, mock_floor):
        """Should return empty list for single floor."""
        floor_nodes = {str(mock_floor.id): [{"id": "n1", "lng": 0.0, "lat": 0.0}]}

        stitched = graph_workflow_service._stitch_adjacent_floors([mock_floor], floor_nodes)

        assert len(stitched) == 0

    def test_stitch_skips_non_adjacent(self, mock_floor):
        """Should not stitch non-adjacent floors."""
        floor2 = MagicMock()
        floor2.id = uuid.uuid4()
        floor2.level_number = 5  # Not adjacent to floor 0

        floor_nodes = {
            str(mock_floor.id): [{"id": "n1", "lng": 0.0, "lat": 0.0}],
            str(floor2.id): [{"id": "n2", "lng": 0.0, "lat": 0.0}]
        }

        stitched = graph_workflow_service._stitch_adjacent_floors([mock_floor, floor2], floor_nodes)

        assert len(stitched) == 0


class TestGetOrCreateNodeType:
    """Tests for _get_or_create_node_type function."""

    @pytest.mark.asyncio
    async def test_get_existing_node_type(self, mock_db_session):
        """Should return existing node type if found."""
        existing = MagicMock()
        existing.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db_session.execute.return_value = mock_result

        result = await graph_workflow_service._get_or_create_node_type(mock_db_session, "corridor")

        assert result == existing

    @pytest.mark.asyncio
    async def test_create_new_node_type(self, mock_db_session):
        """Should create new node type if not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await graph_workflow_service._get_or_create_node_type(mock_db_session, "new_type")

        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()


class TestGetOrCreateEdgeType:
    """Tests for _get_or_create_edge_type function."""

    @pytest.mark.asyncio
    async def test_get_existing_edge_type(self, mock_db_session):
        """Should return existing edge type if found."""
        existing = MagicMock()
        existing.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db_session.execute.return_value = mock_result

        result = await graph_workflow_service._get_or_create_edge_type(mock_db_session, "corridor")

        assert result == existing

    @pytest.mark.asyncio
    async def test_create_new_edge_type(self, mock_db_session):
        """Should create new edge type with accessibility."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await graph_workflow_service._get_or_create_edge_type(
            mock_db_session, "new_edge", is_accessible=False
        )

        mock_db_session.add.assert_called_once()


class TestGetActiveGraphVersion:
    """Tests for get_active_graph_version function."""

    @pytest.mark.asyncio
    async def test_get_active_version_success(self, mock_db_session, mock_building):
        """Should return active graph version."""
        active_version = MagicMock()
        active_version.is_active = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = active_version
        mock_db_session.execute.return_value = mock_result

        result = await graph_workflow_service.get_active_graph_version(
            mock_db_session, mock_building.id
        )

        assert result == active_version
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_get_active_version_none(self, mock_db_session, mock_building):
        """Should return None if no active version."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await graph_workflow_service.get_active_graph_version(
            mock_db_session, mock_building.id
        )

        assert result is None


class TestBuildGraphPreview:
    """Tests for build_graph_preview_for_building function."""

    @pytest.mark.asyncio
    async def test_build_preview_success(self, mock_db_session, mock_building, mock_floor):
        """Should build preview with nodes, edges, and summary."""
        with patch.object(mock_db_session, 'get', return_value=mock_building):
            with patch('services.graph_workflow_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = [mock_floor]
                mock_db_session.execute.return_value = mock_result

                with patch('services.graph_workflow_service.build_navigation_graph') as mock_build_graph:
                    G = nx.Graph()
                    G.add_node((0.0, 0.0), type="corridor")
                    mock_build_graph.return_value = G

                    result = await graph_workflow_service.build_graph_preview_for_building(
                        mock_db_session, mock_building.id
                    )

                    assert "nodes" in result
                    assert "edges" in result
                    assert "summary" in result
                    assert result["building_id"] == str(mock_building.id)

    @pytest.mark.asyncio
    async def test_build_preview_building_not_found(self, mock_db_session):
        """Should raise ValueError when building not found."""
        with patch.object(mock_db_session, 'get', return_value=None):
            with pytest.raises(ValueError, match="Building not found"):
                await graph_workflow_service.build_graph_preview_for_building(
                    mock_db_session, uuid.uuid4()
                )

    @pytest.mark.asyncio
    async def test_build_preview_no_floors(self, mock_db_session, mock_building):
        """Should raise ValueError when no floors found."""
        with patch.object(mock_db_session, 'get', return_value=mock_building):
            with patch('services.graph_workflow_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                mock_db_session.execute.return_value = mock_result

                with pytest.raises(ValueError, match="No floors found"):
                    await graph_workflow_service.build_graph_preview_for_building(
                        mock_db_session, mock_building.id
                    )

    @pytest.mark.asyncio
    async def test_build_preview_multi_floor(self, mock_db_session, mock_building, mock_floor, mock_floor_upper):
        """Should handle multiple floors with stitching."""
        with patch.object(mock_db_session, 'get', return_value=mock_building):
            with patch('services.graph_workflow_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = [mock_floor, mock_floor_upper]
                mock_db_session.execute.return_value = mock_result

                with patch('services.graph_workflow_service.build_navigation_graph') as mock_build_graph:
                    G = nx.Graph()
                    G.add_node((0.0, 0.0), type="corridor")
                    mock_build_graph.return_value = G

                    result = await graph_workflow_service.build_graph_preview_for_building(
                        mock_db_session, mock_building.id
                    )

                    assert result["summary"]["floors_processed"] == 2


class TestConfirmGraphPreview:
    """Tests for confirm_graph_preview function."""

    @pytest.mark.asyncio
    async def test_confirm_preview_success(self, mock_db_session, mock_building, mock_graph_version):
        """Should create new graph version and persist nodes/edges."""
        preview = {
            "nodes": [
                {"id": "n1", "floor_id": str(uuid.uuid4()), "lng": 0.0, "lat": 0.0, "node_type": "corridor"}
            ],
            "edges": [],
            "summary": {"floors_processed": 1}
        }

        with patch.object(graph_workflow_service, 'get_active_graph_version', return_value=mock_graph_version):
            with patch('services.graph_workflow_service.func') as mock_func:
                mock_func.max.return_value = 1

                mock_max_result = MagicMock()
                mock_max_result.scalar.return_value = 1
                mock_db_session.execute.return_value = mock_max_result

                with patch('services.graph_workflow_service.NavigationGraphVersion') as mock_version_class:
                    new_version = MagicMock()
                    new_version.id = uuid.uuid4()
                    new_version.version_number = 2
                    mock_version_class.return_value = new_version

                    with patch.object(graph_workflow_service, '_get_or_create_node_type') as mock_get_node_type:
                        node_type = MagicMock()
                        node_type.id = uuid.uuid4()
                        mock_get_node_type.return_value = node_type

                        result = await graph_workflow_service.confirm_graph_preview(
                            mock_db_session, mock_building.id, preview
                        )

                        assert "graph_version_id" in result
                        assert result["persisted"]["nodes"] == 1


class TestRollbackToPreviousVersion:
    """Tests for rollback_to_previous_graph_version function."""

    @pytest.mark.asyncio
    async def test_rollback_success(self, mock_db_session, mock_building):
        """Should rollback to previous version."""
        active_version = MagicMock()
        active_version.id = uuid.uuid4()
        active_version.version_number = 2
        active_version.is_active = True

        previous_version = MagicMock()
        previous_version.id = uuid.uuid4()
        previous_version.version_number = 1
        previous_version.is_active = False

        with patch('services.graph_workflow_service.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [active_version, previous_version]
            mock_db_session.execute.return_value = mock_result

            result = await graph_workflow_service.rollback_to_previous_graph_version(
                mock_db_session, mock_building.id
            )

            assert result["rolled_back_to_version_number"] == 1
            assert result["previous_active_version_number"] == 2

    @pytest.mark.asyncio
    async def test_rollback_no_previous(self, mock_db_session, mock_building):
        """Should raise ValueError if only one version exists."""
        active_version = MagicMock()
        active_version.version_number = 1

        with patch('services.graph_workflow_service.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [active_version]
            mock_db_session.execute.return_value = mock_result

            with pytest.raises(ValueError, match="No previous graph version"):
                await graph_workflow_service.rollback_to_previous_graph_version(
                    mock_db_session, mock_building.id
                )

    @pytest.mark.asyncio
    async def test_rollback_no_active(self, mock_db_session, mock_building):
        """Should raise ValueError if no active version."""
        inactive_version = MagicMock()
        inactive_version.is_active = False

        with patch('services.graph_workflow_service.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [inactive_version]
            mock_db_session.execute.return_value = mock_result

            with pytest.raises(ValueError, match="No active graph version"):
                await graph_workflow_service.rollback_to_previous_graph_version(
                    mock_db_session, mock_building.id
                )
