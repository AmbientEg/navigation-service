"""Unit tests for the graph pipeline (step2_construct_graph.py)."""

import pytest
import networkx as nx
from pipeline.step2_construct_graph import (
    build_navigation_graph,
    load_geojson_from_dict,
    graph_to_geojson_dict,
    classify_features,
    snap,
    remove_self_loops,
    remove_zero_length_edges,
)


class TestLoadGeoJSON:
    """Tests for GeoJSON loading and validation."""

    def test_load_valid_geojson(self, simple_corridor_geojson):
        """Should accept valid FeatureCollection GeoJSON."""
        result = load_geojson_from_dict(simple_corridor_geojson)
        assert result["type"] == "FeatureCollection"
        assert "features" in result
        assert len(result["features"]) == 1

    def test_load_empty_geojson(self, empty_geojson):
        """Should handle empty FeatureCollection."""
        result = load_geojson_from_dict(empty_geojson)
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []

    def test_load_invalid_not_dict(self):
        """Should reject non-dict input."""
        with pytest.raises(ValueError, match="GeoJSON must be a dictionary"):
            load_geojson_from_dict("not a dict")

    def test_load_invalid_not_feature_collection(self, non_feature_collection_geojson):
        """Should reject non-FeatureCollection types."""
        with pytest.raises(ValueError, match="GeoJSON must be a FeatureCollection"):
            load_geojson_from_dict(non_feature_collection_geojson)

    def test_load_invalid_missing_features(self, invalid_geojson):
        """Should add empty features list if missing."""
        result = load_geojson_from_dict(invalid_geojson)
        assert result["features"] == []


class TestClassifyFeatures:
    """Tests for GeoJSON feature classification."""

    def test_classify_corridor(self, simple_corridor_geojson):
        """Should classify corridor LineString correctly."""
        corridors, doors, rooms, walls = classify_features(simple_corridor_geojson)
        assert len(corridors) == 1
        assert len(doors) == 0
        assert len(rooms) == 0
        assert corridors[0][1]["space_type"] == "corridor"

    def test_classify_door(self, corridor_with_door_geojson):
        """Should classify door LineString correctly."""
        corridors, doors, rooms, walls = classify_features(corridor_with_door_geojson)
        assert len(corridors) == 1
        assert len(doors) == 1
        assert doors[0][1]["space_type"] == "door"

    def test_classify_room_polygon(self, corridor_with_room_geojson):
        """Should classify room Polygon correctly."""
        corridors, doors, rooms, walls = classify_features(corridor_with_room_geojson)
        assert len(rooms) == 1
        assert rooms[0][1]["space_type"] == "office"

    def test_classify_stairs_as_door(self, stairs_connector_geojson):
        """Should classify stairs as doors (vertical connectors)."""
        corridors, doors, rooms, walls = classify_features(stairs_connector_geojson)
        assert len(doors) == 1
        assert doors[0][1]["space_type"] == "stairs"

    def test_classify_empty(self, empty_geojson):
        """Should handle empty feature collection."""
        corridors, doors, rooms, walls = classify_features(empty_geojson)
        assert len(corridors) == 0
        assert len(doors) == 0
        assert len(rooms) == 0


class TestBuildNavigationGraph:
    """Tests for the main graph construction function."""

    def test_build_simple_corridor_graph(self, simple_corridor_geojson):
        """Should build graph from simple corridor."""
        G = build_navigation_graph(simple_corridor_geojson)
        assert isinstance(G, nx.Graph)
        assert len(G.nodes) > 0
        assert len(G.edges) > 0

    def test_build_graph_with_door(self, corridor_with_door_geojson):
        """Should attach door nodes to corridor."""
        G = build_navigation_graph(corridor_with_door_geojson)
        # Check for door nodes
        door_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "door"]
        assert len(door_nodes) >= 1

    def test_build_graph_with_room(self, corridor_with_room_geojson):
        """Should attach room nodes to doors."""
        G = build_navigation_graph(corridor_with_room_geojson)
        room_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "room"]
        assert len(room_nodes) >= 1

    def test_build_graph_creates_junctions(self, multi_corridor_junction_geojson):
        """Should create junction nodes where corridors intersect."""
        G = build_navigation_graph(multi_corridor_junction_geojson)
        # Should have a junction node at (0, 0)
        junction_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "junction"]
        assert len(junction_nodes) >= 1

    def test_build_empty_graph(self, empty_geojson):
        """Should create empty graph from empty GeoJSON."""
        G = build_navigation_graph(empty_geojson)
        assert isinstance(G, nx.Graph)
        assert len(G.nodes) == 0
        assert len(G.edges) == 0

    def test_graph_connectivity_simple(self, simple_corridor_geojson):
        """Simple corridor should be connected."""
        G = build_navigation_graph(simple_corridor_geojson)
        assert nx.is_connected(G)

    def test_graph_node_attributes(self, corridor_with_door_geojson):
        """Nodes should have correct attributes."""
        G = build_navigation_graph(corridor_with_door_geojson)
        for node, attrs in G.nodes(data=True):
            assert "type" in attrs
            if attrs["type"] == "door":
                assert "name" in attrs

    def test_graph_edge_weights(self, simple_corridor_geojson):
        """Edges should have distance weights."""
        G = build_navigation_graph(simple_corridor_geojson)
        for u, v, attrs in G.edges(data=True):
            assert "weight" in attrs
            assert attrs["weight"] > 0


class TestGraphCleanup:
    """Tests for graph cleanup operations."""

    def test_remove_self_loops(self, graph_with_self_loops):
        """Should remove self-loop edges."""
        G = graph_with_self_loops
        initial_loops = len(list(nx.selfloop_edges(G)))
        assert initial_loops > 0
        remove_self_loops(G)
        remaining_loops = len(list(nx.selfloop_edges(G)))
        assert remaining_loops == 0

    def test_remove_zero_length_edges(self, graph_with_zero_edges):
        """Should remove zero-weight edges."""
        G = graph_with_zero_edges
        remove_zero_length_edges(G)
        for u, v, attrs in G.edges(data=True):
            assert attrs.get("weight", 0) > 0

    def test_remove_zero_length_edges_with_threshold(self):
        """Should respect threshold parameter."""
        G = nx.Graph()
        G.add_node("a")
        G.add_node("b")
        G.add_node("c")
        G.add_edge("a", "b", weight=0.0000001)  # Below default threshold
        G.add_edge("b", "c", weight=0.1)  # Above threshold
        remove_zero_length_edges(G, threshold=1e-9)
        assert G.has_edge("b", "c")


class TestGraphExport:
    """Tests for graph to GeoJSON export."""

    def test_export_simple_graph(self, simple_connected_graph):
        """Should export graph to valid GeoJSON."""
        G = simple_connected_graph
        geojson = graph_to_geojson_dict(G)
        assert geojson["type"] == "FeatureCollection"
        assert "features" in geojson
        # Should have nodes as Points and edges as LineStrings
        point_features = [f for f in geojson["features"] if f["geometry"]["type"] == "Point"]
        line_features = [f for f in geojson["features"] if f["geometry"]["type"] == "LineString"]
        assert len(point_features) == len(G.nodes)
        assert len(line_features) == len(G.edges)

    def test_export_empty_graph(self):
        """Should handle empty graph export."""
        G = nx.Graph()
        geojson = graph_to_geojson_dict(G)
        assert geojson["type"] == "FeatureCollection"
        assert geojson["features"] == []

    def test_export_node_properties(self, simple_connected_graph):
        """Exported nodes should have correct properties."""
        G = simple_connected_graph
        geojson = graph_to_geojson_dict(G)
        point_features = [f for f in geojson["features"] if f["geometry"]["type"] == "Point"]
        for feature in point_features:
            assert "node_id" in feature["properties"]
            assert "node_type" in feature["properties"]

    def test_export_edge_properties(self, simple_connected_graph):
        """Exported edges should have correct properties."""
        G = simple_connected_graph
        geojson = graph_to_geojson_dict(G)
        line_features = [f for f in geojson["features"] if f["geometry"]["type"] == "LineString"]
        for feature in line_features:
            assert "edge_id" in feature["properties"]
            assert "weight" in feature["properties"]


class TestCoordinateSnapping:
    """Tests for coordinate precision handling."""

    def test_snap_precision(self):
        """Should round coordinates to PRECISION decimal places."""
        from pipeline.step2_construct_graph import PRECISION
        coord = (1.123456789, 2.987654321)
        snapped = snap(coord)
        assert len(str(snapped[0]).split(".")[-1]) <= PRECISION
        assert len(str(snapped[1]).split(".")[-1]) <= PRECISION

    def test_snap_same_coordinates_merge(self):
        """Very close coordinates should snap to same value."""
        coord1 = (1.000000001, 2.000000001)
        coord2 = (1.000000002, 2.000000002)
        assert snap(coord1) == snap(coord2)
