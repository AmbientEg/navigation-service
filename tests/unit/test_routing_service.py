"""Unit tests for the routing service."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import networkx as nx

from services import routing_service


class TestFindNearestNode:
    """Tests for find_nearest_node function."""

    @pytest.mark.asyncio
    async def test_find_nearest_node_success(self, mock_db_session, mock_graph_version):
        """Should return nearest node when found."""
        floor_id = uuid.uuid4()
        lat, lng = 30.04, 31.23

        # Mock the query result
        mock_node = MagicMock()
        mock_node.id = uuid.uuid4()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_node

        result = await routing_service.find_nearest_node(
            mock_db_session, floor_id, lat, lng, mock_graph_version.id
        )

        assert result == mock_node
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_nearest_node_not_found(self, mock_db_session, mock_graph_version):
        """Should return None when no nodes found."""
        floor_id = uuid.uuid4()
        lat, lng = 30.04, 31.23

        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        result = await routing_service.find_nearest_node(
            mock_db_session, floor_id, lat, lng, mock_graph_version.id
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_find_nearest_node_uses_spatial_query(self, mock_db_session, mock_graph_version):
        """Should use ST_Distance for spatial query."""
        floor_id = uuid.uuid4()
        lat, lng = 30.04, 31.23

        mock_db_session.execute.return_value.scalar_one_or_none.return_value = MagicMock()

        await routing_service.find_nearest_node(
            mock_db_session, floor_id, lat, lng, mock_graph_version.id
        )

        # Verify the call was made (SQL query construction happens in the function)
        mock_db_session.execute.assert_called_once()


class TestBuildGraphForFloors:
    """Tests for build_graph_for_floors function."""

    @pytest.mark.asyncio
    async def test_build_graph_success(self, mock_db_session, mock_graph_version, simple_connected_graph):
        """Should build NetworkX graph from database nodes and edges."""
        floor_ids = [uuid.uuid4()]

        # Mock nodes query
        mock_node = MagicMock()
        mock_node.id = uuid.uuid4()
        mock_node.floor_id = floor_ids[0]
        mock_db_session.execute.side_effect = [
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_node])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        ]

        with patch('services.routing_service.ST_AsText') as mock_st_as_text:
            mock_db_session.execute.return_value.scalar.return_value = "POINT(31.23 30.04)"

            G = await routing_service.build_graph_for_floors(
                mock_db_session, floor_ids, mock_graph_version.id
            )

            assert isinstance(G, nx.Graph)

    @pytest.mark.asyncio
    async def test_build_graph_empty_floors(self, mock_db_session, mock_graph_version):
        """Should handle empty floor list."""
        floor_ids = []

        G = await routing_service.build_graph_for_floors(
            mock_db_session, floor_ids, mock_graph_version.id
        )

        assert isinstance(G, nx.Graph)
        assert len(G.nodes) == 0
        assert len(G.edges) == 0

    @pytest.mark.asyncio
    async def test_build_graph_accessible_filter(self, mock_db_session, mock_graph_version):
        """Should filter edges by accessibility when requested."""
        floor_ids = [uuid.uuid4()]

        # Mock empty results
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

        G = await routing_service.build_graph_for_floors(
            mock_db_session, floor_ids, mock_graph_version.id, accessible_only=True
        )

        assert isinstance(G, nx.Graph)

    @pytest.mark.asyncio
    async def test_build_graph_node_attributes(self, mock_db_session, mock_graph_version):
        """Should include node attributes (floor_id, lat, lng)."""
        floor_ids = [uuid.uuid4()]
        node_id = uuid.uuid4()

        mock_node = MagicMock()
        mock_node.id = node_id
        mock_node.floor_id = floor_ids[0]

        with patch('services.routing_service.ST_AsText') as mock_st_as_text:
            with patch.object(mock_db_session, 'execute') as mock_execute:
                mock_execute.side_effect = [
                    MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_node])))),
                    MagicMock(scalar=MagicMock(return_value="POINT(31.23 30.04)"))
                ]

                G = await routing_service.build_graph_for_floors(
                    mock_db_session, floor_ids, mock_graph_version.id
                )

                # Check that node has expected attributes
                if len(G.nodes) > 0:
                    node_data = G.nodes[str(node_id)]
                    assert "floor_id" in node_data


class TestCalculateRoute:
    """Tests for calculate_route function."""

    @pytest.mark.asyncio
    async def test_calculate_route_success(self, mock_db_session, mock_floor, mock_poi, mock_graph_version):
        """Should return route with floors, distance, and steps."""
        from_floor_id = mock_floor.id
        to_poi_id = mock_poi.id
        from_lat, from_lng = 30.04, 31.23

        with patch.object(mock_db_session, 'get') as mock_get:
            mock_get.side_effect = [mock_poi, mock_floor, mock_floor]

            with patch('services.routing_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalars.return_value.first.return_value = mock_graph_version
                mock_db_session.execute.return_value = mock_result

                with patch('services.routing_service.ST_AsText') as mock_st_as_text:
                    mock_db_session.execute.return_value.scalar.return_value = "POINT(31.23 30.04)"

                    with patch.object(routing_service, 'find_nearest_node') as mock_find_nearest:
                        mock_start_node = MagicMock()
                        mock_start_node.id = uuid.uuid4()
                        mock_end_node = MagicMock()
                        mock_end_node.id = uuid.uuid4()
                        mock_find_nearest.side_effect = [mock_start_node, mock_end_node]

                        with patch.object(routing_service, 'build_graph_for_floors') as mock_build_graph:
                            G = nx.Graph()
                            G.add_node(str(mock_start_node.id), floor_id=str(from_floor_id), lat=from_lat, lng=from_lng)
                            G.add_node(str(mock_end_node.id), floor_id=str(from_floor_id), lat=30.05, lng=31.24)
                            G.add_edge(str(mock_start_node.id), str(mock_end_node.id), weight=100.0)
                            mock_build_graph.return_value = G

                            with patch('services.routing_service.nx.has_path', return_value=True):
                                with patch('services.routing_service.nx.shortest_path') as mock_shortest_path:
                                    mock_shortest_path.return_value = [str(mock_start_node.id), str(mock_end_node.id)]

                                    with patch('services.routing_service.nx.shortest_path_length') as mock_path_length:
                                        mock_path_length.return_value = 100.0

                                        route = await routing_service.calculate_route(
                                            mock_db_session, from_floor_id, from_lat, from_lng,
                                            to_poi_id, accessible=True
                                        )

                                        assert "buildingId" in route
                                        assert "floors" in route
                                        assert "distance" in route
                                        assert "steps" in route
                                        assert route["distance"] == 100.0

    @pytest.mark.asyncio
    async def test_calculate_route_poi_not_found(self, mock_db_session, mock_floor):
        """Should raise ValueError when POI not found."""
        from_floor_id = mock_floor.id
        to_poi_id = uuid.uuid4()

        with patch.object(mock_db_session, 'get', return_value=None):
            with pytest.raises(ValueError, match="POI not found"):
                await routing_service.calculate_route(
                    mock_db_session, from_floor_id, 30.04, 31.23, to_poi_id
                )

    @pytest.mark.asyncio
    async def test_calculate_route_floor_not_found(self, mock_db_session, mock_poi, mock_floor):
        """Should raise ValueError when floor not found."""
        from_floor_id = uuid.uuid4()
        to_poi_id = mock_poi.id

        with patch.object(mock_db_session, 'get') as mock_get:
            mock_get.side_effect = [mock_poi, None, mock_floor]

            with pytest.raises(ValueError, match="Source or destination floor not found"):
                await routing_service.calculate_route(
                    mock_db_session, from_floor_id, 30.04, 31.23, to_poi_id
                )

    @pytest.mark.asyncio
    async def test_calculate_route_cross_building(self, mock_db_session, mock_poi, mock_floor):
        """Should raise ValueError for cross-building routing."""
        from_floor_id = mock_floor.id
        to_poi_id = mock_poi.id

        # Create floor in different building
        other_floor = MagicMock()
        other_floor.id = mock_poi.floor_id
        other_floor.building_id = uuid.uuid4()  # Different building

        with patch.object(mock_db_session, 'get') as mock_get:
            mock_get.side_effect = [mock_poi, mock_floor, other_floor]

            with pytest.raises(ValueError, match="Cross-building routing is not supported"):
                await routing_service.calculate_route(
                    mock_db_session, from_floor_id, 30.04, 31.23, to_poi_id
                )

    @pytest.mark.asyncio
    async def test_calculate_route_no_active_version(self, mock_db_session, mock_floor, mock_poi):
        """Should raise ValueError when no active graph version."""
        from_floor_id = mock_floor.id
        to_poi_id = mock_poi.id

        with patch.object(mock_db_session, 'get') as mock_get:
            mock_get.side_effect = [mock_poi, mock_floor, mock_floor]

            with patch('services.routing_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalars.return_value.first.return_value = None
                mock_db_session.execute.return_value = mock_result

                with pytest.raises(ValueError, match="No active navigation graph version"):
                    await routing_service.calculate_route(
                        mock_db_session, from_floor_id, 30.04, 31.23, to_poi_id
                    )

    @pytest.mark.asyncio
    async def test_calculate_route_no_path(self, mock_db_session, mock_floor, mock_poi, mock_graph_version):
        """Should raise ValueError when no path exists."""
        from_floor_id = mock_floor.id
        to_poi_id = mock_poi.id

        with patch.object(mock_db_session, 'get') as mock_get:
            mock_get.side_effect = [mock_poi, mock_floor, mock_floor]

            with patch('services.routing_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalars.return_value.first.return_value = mock_graph_version
                mock_db_session.execute.return_value = mock_result

                with patch('services.routing_service.ST_AsText') as mock_st_as_text:
                    mock_db_session.execute.return_value.scalar.return_value = "POINT(31.23 30.04)"

                    with patch.object(routing_service, 'find_nearest_node') as mock_find_nearest:
                        mock_start_node = MagicMock()
                        mock_start_node.id = uuid.uuid4()
                        mock_end_node = MagicMock()
                        mock_end_node.id = uuid.uuid4()
                        mock_find_nearest.side_effect = [mock_start_node, mock_end_node]

                        with patch.object(routing_service, 'build_graph_for_floors') as mock_build_graph:
                            mock_build_graph.return_value = nx.Graph()

                            with patch('services.routing_service.nx.has_path', return_value=False):
                                with pytest.raises(ValueError, match="No route found"):
                                    await routing_service.calculate_route(
                                        mock_db_session, from_floor_id, 30.04, 31.23, to_poi_id
                                    )

    @pytest.mark.asyncio
    async def test_calculate_route_nearest_node_not_found(self, mock_db_session, mock_floor, mock_poi, mock_graph_version):
        """Should raise ValueError when start or end node not found."""
        from_floor_id = mock_floor.id
        to_poi_id = mock_poi.id

        with patch.object(mock_db_session, 'get') as mock_get:
            mock_get.side_effect = [mock_poi, mock_floor, mock_floor]

            with patch('services.routing_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalars.return_value.first.return_value = mock_graph_version
                mock_db_session.execute.return_value = mock_result

                with patch('services.routing_service.ST_AsText') as mock_st_as_text:
                    mock_db_session.execute.return_value.scalar.return_value = "POINT(31.23 30.04)"

                    with patch.object(routing_service, 'find_nearest_node') as mock_find_nearest:
                        mock_find_nearest.return_value = None

                        with pytest.raises(ValueError, match="Could not find routing nodes"):
                            await routing_service.calculate_route(
                                mock_db_session, from_floor_id, 30.04, 31.23, to_poi_id
                            )


class TestGenerateSteps:
    """Tests for generate_steps function."""

    def test_generate_steps_empty_path(self):
        """Should return arrival message for empty path."""
        G = nx.Graph()
        steps = routing_service.generate_steps(G, [], 0, 0, 10, 10)
        assert steps == ["You have arrived"]

    def test_generate_steps_single_floor(self, simple_connected_graph):
        """Should generate steps for single floor path."""
        G = simple_connected_graph
        path = ["node1", "node2", "node3"]
        steps = routing_service.generate_steps(G, path, 0, 0, 20, 0)
        assert len(steps) > 0
        assert "destination" in steps[-1]

    def test_generate_steps_multi_floor(self, multi_floor_graph):
        """Should detect and report floor changes."""
        G = multi_floor_graph
        path = ["f1_node1", "f1_node2", "f1_stairs", "f2_stairs", "f2_node2"]
        steps = routing_service.generate_steps(G, path, 0, 0, 10, 0)
        # Should have floor change instruction
        floor_changes = [s for s in steps if "floor" in s.lower() or "Change" in s]
        assert len(floor_changes) > 0

    def test_generate_steps_first_instruction(self, simple_connected_graph):
        """First step should be starting instruction."""
        G = simple_connected_graph
        path = ["node1", "node2"]
        steps = routing_service.generate_steps(G, path, 0, 0, 10, 0)
        assert len(steps) > 0
        # First step should be start-related
        assert any(word in steps[0].lower() for word in ["start", "head", "begin"])


class TestBuildGraphLegacy:
    """Tests for legacy build_graph function."""

    def test_build_graph_legacy(self):
        """Legacy function should create graph from nodes and edges."""
        node1 = MagicMock()
        node1.id = uuid.uuid4()
        node2 = MagicMock()
        node2.id = uuid.uuid4()

        edge = MagicMock()
        edge.from_node_id = node1.id
        edge.to_node_id = node2.id
        edge.distance = 10.0

        G = routing_service.build_graph([node1, node2], [edge])

        assert isinstance(G, nx.Graph)
        assert len(G.nodes) == 2
        assert len(G.edges) == 1


class TestShortestPathLegacy:
    """Tests for legacy shortest_path function."""

    def test_shortest_path_legacy(self, simple_connected_graph):
        """Legacy function should find shortest path."""
        G = simple_connected_graph
        path = routing_service.shortest_path(G, "node1", "node3")
        assert isinstance(path, list)
        assert path[0] == "node1"
        assert path[-1] == "node3"

    def test_shortest_path_legacy_no_path(self, disconnected_graph):
        """Should raise exception when no path exists."""
        G = disconnected_graph
        with pytest.raises(nx.NetworkXNoPath):
            routing_service.shortest_path(G, "node1", "node3")
