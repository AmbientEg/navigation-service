import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select, text
from geoalchemy2.functions import ST_AsText

from database import db_manager
from models import Base
from models.poi import POI
from services.crs_service import validate_wgs84_coordinates
from services.graph_persistence_service import persist_pipeline_output
from services.routing_service import calculate_route, find_nearest_node

ROOT = Path(__file__).resolve().parent
PIPELINE_DIR = ROOT / "pipeline"
GRAPH_VERIFIED_PATH = PIPELINE_DIR / "navigation_graph_verified.geojson"
GRAPH_EXPORT_PATH = PIPELINE_DIR / "navigation_graph_export.geojson"
FLOOR3_PATH = PIPELINE_DIR / "floor3.geojson"


def _resolve_graph_path() -> Path:
    if GRAPH_VERIFIED_PATH.exists():
        return GRAPH_VERIFIED_PATH
    return GRAPH_EXPORT_PATH


async def _ensure_tables() -> None:
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE routing_nodes ADD COLUMN IF NOT EXISTS name VARCHAR(255)"))


async def _poi_coords(db, poi_id: uuid.UUID) -> tuple[float, float]:
    result = await db.execute(select(ST_AsText(POI.geometry)).where(POI.id == poi_id))
    wkt = result.scalar_one()
    lng, lat = wkt.replace("POINT(", "").replace(")", "").split()
    return float(lng), float(lat)


def _print_route(route: dict) -> None:
    print("\nRoute output:")
    print(f"  distance: {route['distance']} m")
    print("  floors/path:")
    for floor in route["floors"]:
        print(f"    floorId={floor['floorId']} points={len(floor['path'])}")
    print("  steps:")
    for i, step in enumerate(route["steps"], start=1):
        print(f"    {i}. {step}")


async def main() -> None:
    graph_path = _resolve_graph_path()
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph file not found: {graph_path}")
    if not FLOOR3_PATH.exists():
        raise FileNotFoundError(f"Floor file not found: {FLOOR3_PATH}")

    await db_manager.initialize()
    await _ensure_tables()

    anomalies: list[str] = []

    try:
        async with db_manager.get_session() as db:
            print("[1/5] Persisting floor3 + graph into DB...")
            persist_result = await persist_pipeline_output(
                db=db,
                graph_geojson_path=str(graph_path),
                floor_geojson_path=str(FLOOR3_PATH),
                building_name=f"floor3-routing-test-{uuid.uuid4().hex[:8]}",
                building_description="Runtime route test on floor3.geojson",
                floor_level=3,
                floor_name="3rd Floor",
                floor_height=3.0,
                clear_existing_floor_data=True,
            )

            floor_id = uuid.UUID(persist_result["floor_id"])
            print("Persist summary:")
            print(f"  floor_id={floor_id}")
            print(f"  nodes={persist_result['routing_nodes_inserted']}")
            print(f"  edges={persist_result['routing_edges_inserted']}")
            print(f"  pois={persist_result['pois_inserted']}")

            if persist_result["routing_nodes_inserted"] == 0:
                raise AssertionError("No routing nodes persisted for floor3")
            if persist_result["routing_edges_inserted"] == 0:
                raise AssertionError("No routing edges persisted for floor3")
            if persist_result["pois_inserted"] < 2:
                raise AssertionError("Need at least 2 POIs to run route test")

            print("[2/5] Loading POIs from persisted floor...")
            pois_result = await db.execute(select(POI).where(POI.floor_id == floor_id).order_by(POI.name.asc()))
            pois = pois_result.scalars().all()
            source_poi = pois[0]
            destination_poi = pois[1]
            print(f"  source_poi={source_poi.name} ({source_poi.id})")
            print(f"  destination_poi={destination_poi.name} ({destination_poi.id})")

            source_lng, source_lat = await _poi_coords(db, source_poi.id)
            if not validate_wgs84_coordinates(source_lng, source_lat):
                anomalies.append(f"Source POI invalid WGS84: ({source_lng}, {source_lat})")

            print("[3/5] Validating nearest-node mapping...")
            nearest = await find_nearest_node(db, floor_id, source_lat, source_lng)
            if nearest is None:
                anomalies.append("Nearest node not found for source POI")
            else:
                print(f"  nearest_node={nearest.id} name={nearest.name}")

            print("[4/5] Computing route using routing_service.calculate_route()...")
            route = await calculate_route(
                db=db,
                from_floor_id=floor_id,
                from_lat=source_lat,
                from_lng=source_lng,
                to_poi_id=destination_poi.id,
                accessible=True,
            )
            _print_route(route)

            # Assertions / checks
            if route["distance"] <= 0:
                anomalies.append("Route distance must be > 0")
            if not route["steps"]:
                anomalies.append("Route steps are empty")
            if "arrived" not in route["steps"][-1].lower():
                anomalies.append("Route does not end with arrival instruction")

            # Coordinate sanity check for returned path
            for floor_path in route["floors"]:
                for lng, lat in floor_path["path"]:
                    if not validate_wgs84_coordinates(lng, lat):
                        anomalies.append(f"Invalid route coordinate: ({lng}, {lat})")

            # Edge case: invalid incoming coordinate should fail fast
            print("[5/5] Running edge-case checks...")
            try:
                await calculate_route(
                    db=db,
                    from_floor_id=floor_id,
                    from_lat=999.0,
                    from_lng=source_lng,
                    to_poi_id=destination_poi.id,
                    accessible=True,
                )
                anomalies.append("Invalid coordinate edge case did not fail")
            except ValueError as e:
                print(f"  invalid-lat edge case: OK ({e})")

            try:
                await calculate_route(
                    db=db,
                    from_floor_id=uuid.uuid4(),
                    from_lat=source_lat,
                    from_lng=source_lng,
                    to_poi_id=destination_poi.id,
                    accessible=True,
                )
                anomalies.append("Unknown floor edge case did not fail")
            except ValueError as e:
                print(f"  unknown-floor edge case: OK ({e})")

        print("\n" + "=" * 70)
        print("FLOOR3 ROUTING TEST SUMMARY")
        print("=" * 70)
        if anomalies:
            print("Anomalies:")
            for i, item in enumerate(anomalies, start=1):
                print(f"  {i}. {item}")
            raise AssertionError(f"Found {len(anomalies)} anomaly/anomalies")

        print("All checks passed on floor3.geojson")
        print("- CRS-safe coordinates verified (WGS84)")
        print("- nearest-node mapping works")
        print("- shortest-path route computed")
        print("- steps generated and valid")
        print("- invalid-input edge cases handled")

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
