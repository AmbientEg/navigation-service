import asyncio
import json
import math
import tempfile
import uuid
from pathlib import Path

import networkx as nx
from sqlalchemy import select, text
from geoalchemy2.functions import ST_AsText

from database import db_manager
from models import Base
from models.edge_types import EdgeType
from models.poi import POI
from models.routing_edges import RoutingEdge
from models.routing_nodes import RoutingNode
from services.crs_service import utm_to_wgs84, validate_wgs84_coordinates, wgs84_to_utm
from services.graph_persistence_service import persist_pipeline_output
from services.routing_service import build_graph_for_floors, calculate_route, find_nearest_node


def _make_feature_point(x: float, y: float, props: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [x, y]},
        "properties": props,
    }


def _make_feature_line(coords: list[list[float]], props: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": props,
    }


def _make_floor_polygon(center_lng: float, center_lat: float, half_size_deg: float = 0.0004) -> dict:
    """Create a tiny WGS84 polygon footprint around a center point."""
    min_lng = center_lng - half_size_deg
    max_lng = center_lng + half_size_deg
    min_lat = center_lat - half_size_deg
    max_lat = center_lat + half_size_deg
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [min_lng, min_lat],
                [min_lng, max_lat],
                [max_lng, max_lat],
                [max_lng, min_lat],
                [min_lng, min_lat],
            ]],
        },
        "properties": {"space_type": "floor_shell"},
    }


async def _create_test_tables_if_needed() -> None:
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Keep compatibility with environments where this column was missing earlier.
        await conn.execute(text("ALTER TABLE routing_nodes ADD COLUMN IF NOT EXISTS name VARCHAR(255)"))


async def _get_node_by_name(db, floor_id: uuid.UUID, name: str) -> RoutingNode:
    result = await db.execute(
        select(RoutingNode)
        .where(RoutingNode.floor_id == floor_id, RoutingNode.name == name)
        .limit(1)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise AssertionError(f"Expected node '{name}' not found on floor {floor_id}")
    return node


async def _get_poi_by_name(db, floor_id: uuid.UUID, name: str) -> POI:
    result = await db.execute(
        select(POI)
        .where(POI.floor_id == floor_id, POI.name == name)
        .limit(1)
    )
    poi = result.scalar_one_or_none()
    if poi is None:
        raise AssertionError(f"Expected POI '{name}' not found on floor {floor_id}")
    return poi


async def _get_edge_type_id(db, code: str) -> uuid.UUID:
    result = await db.execute(select(EdgeType).where(EdgeType.code == code).limit(1))
    edge_type = result.scalar_one_or_none()
    if edge_type is None:
        raise AssertionError(f"EdgeType '{code}' not found")
    return edge_type.id


async def _expected_distance(
    db,
    from_floor_id: uuid.UUID,
    from_lat: float,
    from_lng: float,
    to_poi: POI,
    accessible_only: bool,
) -> float:
    """Compute expected shortest-path distance directly from graph for assertion."""
    # Parse destination WKT point via query for consistency with service behavior.
    poi_wkt_result = await db.execute(select(ST_AsText(POI.geometry)).where(POI.id == to_poi.id))
    poi_wkt = poi_wkt_result.scalar()
    # WKT format: POINT(lng lat)
    coords = poi_wkt.replace("POINT(", "").replace(")", "").split()
    poi_lng, poi_lat = float(coords[0]), float(coords[1])

    start_node = await find_nearest_node(db, from_floor_id, from_lat, from_lng)
    end_node = await find_nearest_node(db, to_poi.floor_id, poi_lat, poi_lng)
    assert start_node is not None and end_node is not None

    G = await build_graph_for_floors(db, [from_floor_id, to_poi.floor_id], accessible_only=accessible_only)
    assert nx.has_path(G, str(start_node.id), str(end_node.id))
    return float(nx.shortest_path_length(G, str(start_node.id), str(end_node.id), weight="weight"))


def _print_route(label: str, route_data: dict) -> None:
    print(f"\n=== {label} ===")
    print(f"Total distance: {route_data['distance']} m")
    print("Path (by floor):")
    for floor_path in route_data["floors"]:
        print(f"  floor={floor_path['floorId']} coords={floor_path['path']}")
    print("Steps:")
    for idx, step in enumerate(route_data["steps"], start=1):
        print(f"  {idx}. {step}")


async def main() -> None:
    await db_manager.initialize()
    await _create_test_tables_if_needed()

    anomalies: list[str] = []

    try:
        async with db_manager.get_session() as db:
            # ------------------------------------------------------------------
            # 1) Build test data for 3 floors (2 connected + 1 isolated)
            # ------------------------------------------------------------------
            run_id = uuid.uuid4().hex[:8]
            building_name = f"routing-e2e-{run_id}"

            # Base point in WGS84 (Cairo-ish), then move to UTM to create metric offsets.
            base_lng, base_lat = 31.2357, 30.0444
            x0, y0, zone = wgs84_to_utm(base_lng, base_lat)
            print(f"Using UTM zone={zone}; base WGS84=({base_lng}, {base_lat})")

            # Floor 1 UTM graph nodes
            f1_nodes = {
                "f1_start": (x0 + 0.0, y0 + 0.0),
                "f1_stairs": (x0 + 10.0, y0 + 0.0),
                "f1_elevator": (x0 + 0.0, y0 + 12.0),
                "f1_room": (x0 + 20.0, y0 + 0.0),
                "f1_invalid": (999999999.0, 999999999.0),  # intentionally invalid
            }

            # Floor 2 UTM graph nodes
            f2_nodes = {
                "f2_stairs": (x0 + 10.0, y0 + 1.0),
                "f2_elevator": (x0 + 0.0, y0 + 13.0),
                "f2_room": (x0 + 20.0, y0 + 1.0),
            }

            # Floor 3 UTM graph nodes (isolated edge-case floor)
            f3_nodes = {
                "f3_isolated": (x0 + 40.0, y0 + 40.0),
            }

            def graph_geojson_for_floor(node_map: dict[str, tuple[float, float]], floor_label: str, with_edges: bool = True) -> dict:
                features: list[dict] = []
                for node_name, (x, y) in node_map.items():
                    node_type = "corridor"
                    if "stairs" in node_name:
                        node_type = "stairs"
                    elif "elevator" in node_name:
                        node_type = "elevator"
                    elif "room" in node_name:
                        node_type = "room"
                    features.append(
                        _make_feature_point(
                            x,
                            y,
                            {
                                "node_id": f"{floor_label}_{node_name}",
                                "node_type": node_type,
                                "name": node_name,
                            },
                        )
                    )

                # Horizontal edges per floor
                if with_edges and floor_label == "f1":
                    a = node_map["f1_start"]
                    b = node_map["f1_stairs"]
                    c = node_map["f1_elevator"]
                    d = node_map["f1_room"]
                    features.extend([
                        _make_feature_line([list(a), list(b)], {"source": "f1_f1_start", "target": "f1_f1_stairs", "weight": 10.0, "edge_type": "corridor"}),
                        _make_feature_line([list(a), list(c)], {"source": "f1_f1_start", "target": "f1_f1_elevator", "weight": 12.0, "edge_type": "corridor"}),
                        _make_feature_line([list(b), list(d)], {"source": "f1_f1_stairs", "target": "f1_f1_room", "weight": 10.0, "edge_type": "corridor"}),
                        _make_feature_line([list(c), list(d)], {"source": "f1_f1_elevator", "target": "f1_f1_room", "weight": 10.0, "edge_type": "corridor"}),
                    ])

                if with_edges and floor_label == "f2":
                    b2 = node_map["f2_stairs"]
                    c2 = node_map["f2_elevator"]
                    d2 = node_map["f2_room"]
                    features.extend([
                        _make_feature_line([list(b2), list(d2)], {"source": "f2_f2_stairs", "target": "f2_f2_room", "weight": 10.0, "edge_type": "corridor"}),
                        _make_feature_line([list(c2), list(d2)], {"source": "f2_f2_elevator", "target": "f2_f2_room", "weight": 10.0, "edge_type": "corridor"}),
                    ])

                return {"type": "FeatureCollection", "features": features}

            # Convert target UTM node locations to WGS84 for POI geometry placement.
            f1_room_lng, f1_room_lat = utm_to_wgs84(*f1_nodes["f1_room"])
            f2_room_lng, f2_room_lat = utm_to_wgs84(*f2_nodes["f2_room"])
            f3_iso_lng, f3_iso_lat = utm_to_wgs84(*f3_nodes["f3_isolated"])

            floor1_geojson = {
                "type": "FeatureCollection",
                "features": [
                    _make_floor_polygon(base_lng, base_lat),
                    _make_feature_point(f1_room_lng, f1_room_lat, {"name": "poi_room_f1", "space_type": "room", "poi": True}),
                ],
            }
            floor2_geojson = {
                "type": "FeatureCollection",
                "features": [
                    _make_floor_polygon(base_lng, base_lat),
                    _make_feature_point(f2_room_lng, f2_room_lat, {"name": "poi_room_f2", "space_type": "room", "poi": True}),
                ],
            }
            floor3_geojson = {
                "type": "FeatureCollection",
                "features": [
                    _make_floor_polygon(base_lng, base_lat),
                    _make_feature_point(f3_iso_lng, f3_iso_lat, {"name": "poi_isolated_f3", "space_type": "room", "poi": True}),
                ],
            }

            floor1_graph = graph_geojson_for_floor(f1_nodes, "f1", with_edges=True)
            floor2_graph = graph_geojson_for_floor(f2_nodes, "f2", with_edges=True)
            floor3_graph = graph_geojson_for_floor(f3_nodes, "f3", with_edges=False)

            with tempfile.TemporaryDirectory(prefix="nav_e2e_") as tmp:
                tmp_path = Path(tmp)

                f1_floor_path = tmp_path / "floor1.geojson"
                f2_floor_path = tmp_path / "floor2.geojson"
                f3_floor_path = tmp_path / "floor3.geojson"
                f1_graph_path = tmp_path / "graph1.geojson"
                f2_graph_path = tmp_path / "graph2.geojson"
                f3_graph_path = tmp_path / "graph3.geojson"

                f1_floor_path.write_text(json.dumps(floor1_geojson), encoding="utf-8")
                f2_floor_path.write_text(json.dumps(floor2_geojson), encoding="utf-8")
                f3_floor_path.write_text(json.dumps(floor3_geojson), encoding="utf-8")
                f1_graph_path.write_text(json.dumps(floor1_graph), encoding="utf-8")
                f2_graph_path.write_text(json.dumps(floor2_graph), encoding="utf-8")
                f3_graph_path.write_text(json.dumps(floor3_graph), encoding="utf-8")

                # ------------------------------------------------------------------
                # 2) Persist floors via graph_persistence_service
                # ------------------------------------------------------------------
                persist_f1 = await persist_pipeline_output(
                    db=db,
                    graph_geojson_path=str(f1_graph_path),
                    floor_geojson_path=str(f1_floor_path),
                    building_name=building_name,
                    building_description="E2E routing test building",
                    floor_level=1,
                    floor_name="Floor 1",
                    floor_height=3.0,
                    clear_existing_floor_data=True,
                )
                persist_f2 = await persist_pipeline_output(
                    db=db,
                    graph_geojson_path=str(f2_graph_path),
                    floor_geojson_path=str(f2_floor_path),
                    building_name=building_name,
                    building_description="E2E routing test building",
                    floor_level=2,
                    floor_name="Floor 2",
                    floor_height=3.0,
                    clear_existing_floor_data=True,
                )
                persist_f3 = await persist_pipeline_output(
                    db=db,
                    graph_geojson_path=str(f3_graph_path),
                    floor_geojson_path=str(f3_floor_path),
                    building_name=building_name,
                    building_description="E2E routing test building",
                    floor_level=3,
                    floor_name="Floor 3",
                    floor_height=3.0,
                    clear_existing_floor_data=True,
                )

                print("\nPersist results:")
                print("F1:", persist_f1)
                print("F2:", persist_f2)
                print("F3:", persist_f3)

                # Assert invalid node skipped on floor 1 (5 in source, 4 should remain)
                assert persist_f1["routing_nodes_inserted"] == 4, (
                    f"Expected 4 persisted nodes on floor1 (invalid skipped), got {persist_f1['routing_nodes_inserted']}"
                )

                floor1_id = uuid.UUID(persist_f1["floor_id"])
                floor2_id = uuid.UUID(persist_f2["floor_id"])
                floor3_id = uuid.UUID(persist_f3["floor_id"])

                # ------------------------------------------------------------------
                # 3) Add cross-floor vertical edges (stairs + elevator)
                # ------------------------------------------------------------------
                f1_stairs_node = await _get_node_by_name(db, floor1_id, "f1_stairs")
                f2_stairs_node = await _get_node_by_name(db, floor2_id, "f2_stairs")
                f1_elevator_node = await _get_node_by_name(db, floor1_id, "f1_elevator")
                f2_elevator_node = await _get_node_by_name(db, floor2_id, "f2_elevator")

                stairs_type_id = await _get_edge_type_id(db, "stairs")      # inaccessible
                elevator_type_id = await _get_edge_type_id(db, "elevator")  # accessible

                db.add(
                    RoutingEdge(
                        from_node_id=f1_stairs_node.id,
                        to_node_id=f2_stairs_node.id,
                        edge_type_id=stairs_type_id,
                        distance=3.0,
                    )
                )
                db.add(
                    RoutingEdge(
                        from_node_id=f1_elevator_node.id,
                        to_node_id=f2_elevator_node.id,
                        edge_type_id=elevator_type_id,
                        distance=8.0,
                    )
                )
                await db.commit()

                # ------------------------------------------------------------------
                # 4) Gather POIs for route tests
                # ------------------------------------------------------------------
                poi_f1 = await _get_poi_by_name(db, floor1_id, "poi_room_f1")
                poi_f2 = await _get_poi_by_name(db, floor2_id, "poi_room_f2")
                poi_f3 = await _get_poi_by_name(db, floor3_id, "poi_isolated_f3")

                # Start location close to f1_start (WGS84)
                start_lng, start_lat = utm_to_wgs84(*f1_nodes["f1_start"])
                assert validate_wgs84_coordinates(start_lng, start_lat)

                # ------------------------------------------------------------------
                # 5) Nearest-node mapping validation
                # ------------------------------------------------------------------
                elev_lng, elev_lat = utm_to_wgs84(*f1_nodes["f1_elevator"])
                nearest = await find_nearest_node(db, floor1_id, elev_lat, elev_lng)
                assert nearest is not None
                print(f"\nNearest node check: expected f1_elevator, got {nearest.name}")
                if nearest.name != "f1_elevator":
                    anomalies.append(f"Nearest-node mismatch near elevator: got {nearest.name}")

                # ------------------------------------------------------------------
                # 6) Route tests
                # ------------------------------------------------------------------
                # Route A: Same-floor to floor1 POI
                route_a = await calculate_route(
                    db=db,
                    from_floor_id=floor1_id,
                    from_lat=start_lat,
                    from_lng=start_lng,
                    to_poi_id=poi_f1.id,
                    accessible=True,
                )
                _print_route("Route A (same floor, accessible=True)", route_a)

                expected_a = await _expected_distance(db, floor1_id, start_lat, start_lng, poi_f1, accessible_only=True)
                assert math.isclose(route_a["distance"], expected_a, rel_tol=1e-9), (
                    f"Distance mismatch Route A: got {route_a['distance']}, expected {expected_a}"
                )

                # Route B: Multi-floor, accessible=True (must prefer elevator over stairs)
                route_b = await calculate_route(
                    db=db,
                    from_floor_id=floor1_id,
                    from_lat=start_lat,
                    from_lng=start_lng,
                    to_poi_id=poi_f2.id,
                    accessible=True,
                )
                _print_route("Route B (multi-floor, accessible=True)", route_b)

                expected_b = await _expected_distance(db, floor1_id, start_lat, start_lng, poi_f2, accessible_only=True)
                assert math.isclose(route_b["distance"], expected_b, rel_tol=1e-9), (
                    f"Distance mismatch Route B: got {route_b['distance']}, expected {expected_b}"
                )
                if not any("Change to floor" in s for s in route_b["steps"]):
                    anomalies.append("Route B missing floor transition step")

                # Route C: Multi-floor, accessible=False (stairs allowed; should be shorter)
                route_c = await calculate_route(
                    db=db,
                    from_floor_id=floor1_id,
                    from_lat=start_lat,
                    from_lng=start_lng,
                    to_poi_id=poi_f2.id,
                    accessible=False,
                )
                _print_route("Route C (multi-floor, accessible=False)", route_c)

                expected_c = await _expected_distance(db, floor1_id, start_lat, start_lng, poi_f2, accessible_only=False)
                assert math.isclose(route_c["distance"], expected_c, rel_tol=1e-9), (
                    f"Distance mismatch Route C: got {route_c['distance']}, expected {expected_c}"
                )
                if route_c["distance"] >= route_b["distance"]:
                    anomalies.append(
                        f"Expected accessible=False route to be shorter (stairs), but got C={route_c['distance']} >= B={route_b['distance']}"
                    )

                # Basic step validity checks
                for label, route in [("A", route_a), ("B", route_b), ("C", route_c)]:
                    if not route["steps"]:
                        anomalies.append(f"Route {label} has empty steps")
                    elif "arrived" not in route["steps"][-1].lower():
                        anomalies.append(f"Route {label} does not end with arrival step")

                # ------------------------------------------------------------------
                # 7) Edge cases
                # ------------------------------------------------------------------
                # Edge case 1: Invalid incoming coordinates (lat out of range)
                try:
                    await calculate_route(
                        db=db,
                        from_floor_id=floor1_id,
                        from_lat=999.0,
                        from_lng=start_lng,
                        to_poi_id=poi_f1.id,
                        accessible=True,
                    )
                    anomalies.append("Invalid coordinate case did not fail as expected")
                except ValueError as e:
                    print(f"\nEdge case (invalid lat/lng) OK: {e}")

                # Edge case 2: Start on floor with no routing nodes
                try:
                    await calculate_route(
                        db=db,
                        from_floor_id=uuid.uuid4(),
                        from_lat=start_lat,
                        from_lng=start_lng,
                        to_poi_id=poi_f1.id,
                        accessible=True,
                    )
                    anomalies.append("Unknown floor case did not fail as expected")
                except ValueError as e:
                    print(f"Edge case (unknown floor) OK: {e}")

                # Edge case 3: No path to isolated floor POI
                try:
                    await calculate_route(
                        db=db,
                        from_floor_id=floor1_id,
                        from_lat=start_lat,
                        from_lng=start_lng,
                        to_poi_id=poi_f3.id,
                        accessible=False,
                    )
                    anomalies.append("No-path case did not fail as expected")
                except ValueError as e:
                    print(f"Edge case (no path) OK: {e}")

        # ----------------------------------------------------------------------
        # Final summary
        # ----------------------------------------------------------------------
        print("\n" + "=" * 72)
        print("FULL NAVIGATION SYSTEM TEST SUMMARY")
        print("=" * 72)
        if anomalies:
            print("Anomalies found:")
            for idx, anomaly in enumerate(anomalies, start=1):
                print(f"  {idx}. {anomaly}")
            raise AssertionError(f"Test completed with {len(anomalies)} anomaly/anomalies")

        print("All assertions passed.")
        print("- CRS normalization validated (invalid UTM-like node skipped)")
        print("- Nearest-node mapping validated")
        print("- Weighted shortest-path validated (distance = sum of edge weights)")
        print("- Multi-floor transitions validated (stairs/elevator behavior)")
        print("- Turn-by-turn heuristic steps validated")
        print("- Edge-case handling validated (invalid input, unknown floor, no path)")
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
