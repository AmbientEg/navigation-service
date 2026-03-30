import asyncio
import json
import os
import subprocess
from pathlib import Path

import httpx
from sqlalchemy import text

from database import db_manager
from main import app


ROOT = Path(__file__).resolve().parent
PIPELINE_DIR = ROOT / "pipeline"
FLOOR3_PATH = PIPELINE_DIR / "floor3.geojson"
GRAPH_VERIFIED_PATH = PIPELINE_DIR / "navigation_graph_verified.geojson"
CENTERLINES_PATH = PIPELINE_DIR / "floor3_centerlines.geojson"


def compute_square_polygon_wkt(geojson_path: Path) -> str:
    with geojson_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    minx, miny = float("inf"), float("inf")
    maxx, maxy = float("-inf"), float("-inf")

    def walk_coords(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)) and len(coords) >= 2:
            x, y = coords[0], coords[1]
            nonlocal minx, miny, maxx, maxy
            minx = min(minx, x)
            miny = min(miny, y)
            maxx = max(maxx, x)
            maxy = max(maxy, y)
            return
        for item in coords:
            walk_coords(item)

    for feature in data.get("features", []):
        geom = feature.get("geometry") or {}
        walk_coords(geom.get("coordinates", []))

    if minx == float("inf"):
        raise ValueError("Could not compute bounds from floor3.geojson")

    pad_x = max((maxx - minx) * 0.05, 0.00001)
    pad_y = max((maxy - miny) * 0.05, 0.00001)

    minx -= pad_x
    miny -= pad_y
    maxx += pad_x
    maxy += pad_y

    return (
        f"POLYGON(({minx} {miny}, {minx} {maxy}, {maxx} {maxy}, "
        f"{maxx} {miny}, {minx} {miny}))"
    )


def run_pipeline_steps_0_to_3():
    steps = [
        "step0_reproject.py",
        "step1_draw_Centerlines.py",
        "step2_construct_graph.py",
        "step3_verify_graph.py",
    ]
    for step in steps:
        result = subprocess.run(
            ["python", step],
            cwd=str(PIPELINE_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Pipeline step failed: {step}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )


async def main():
    os.environ["ADMIN_API_TOKEN"] = os.getenv("ADMIN_API_TOKEN", "test-admin-token")

    # Ensure DB is ready for in-process ASGI calls
    await db_manager.initialize()
    try:
        async with db_manager.engine.begin() as conn:
            from models import Base
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("ALTER TABLE routing_nodes ADD COLUMN IF NOT EXISTS name VARCHAR(255)"))

        print("[1/6] Creating building via /api/admin/buildings ...")
        polygon_wkt = compute_square_polygon_wkt(FLOOR3_PATH)

        headers = {"Authorization": f"Bearer {os.environ['ADMIN_API_TOKEN']}"}
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            building_payload = {
                "name": "Credit FCAI CU",
                "description": "Test building for API persistence",
                "floors_count": 1,
                "geometry_wkt": polygon_wkt,
            }
            r = await client.post("/api/admin/buildings", json=building_payload, headers=headers)
            r.raise_for_status()
            building = r.json()
            building_id = building["id"]

            print("[2/6] Creating floor 3 via /api/admin/floors ...")
            with FLOOR3_PATH.open("r", encoding="utf-8") as f:
                floor_geojson = json.load(f)

            floor_payload = {
                "building_id": building_id,
                "level_number": 3,
                "name": "3rd Floor",
                "height_meters": 2.9,
                "floor_geojson": floor_geojson,
            }
            r = await client.post("/api/admin/floors", json=floor_payload, headers=headers)
            r.raise_for_status()
            floor = r.json()
            floor_id = floor["id"]

            print("[3/6] Running navigation pipeline steps 0-3 ...")
            run_pipeline_steps_0_to_3()

            print("[4/6] Persisting graph via /api/admin/graph/persist ...")
            persist_payload = {
                "graph_geojson_path": str(GRAPH_VERIFIED_PATH),
                "floor_geojson_path": str(CENTERLINES_PATH),
                "building_name": "Credit FCAI CU",
                "floor_level": 3,
                "floor_name": "3rd Floor",
                "floor_height": 2.9,
                "clear_existing_floor_data": True,
            }
            r = await client.post("/api/admin/graph/persist", json=persist_payload, headers=headers)
            r.raise_for_status()
            persist_result = r.json()

            print("[5/6] Verifying persistence via admin GET routes ...")
            rb = await client.get("/api/admin/buildings", headers=headers)
            rb.raise_for_status()
            buildings = rb.json()

            rf = await client.get("/api/admin/floors", headers=headers)
            rf.raise_for_status()
            floors = rf.json()

            rn = await client.get("/api/admin/routing-nodes", headers=headers)
            rn.raise_for_status()
            nodes = rn.json()

            re = await client.get("/api/admin/routing-edges", headers=headers)
            re.raise_for_status()
            edges = re.json()

            rp = await client.get("/api/admin/pois", headers=headers)
            rp.raise_for_status()
            pois = rp.json()

            persisted_floor_id = persist_result.get("floor_id")
            nodes_for_floor = [n for n in nodes if n.get("floor_id") == persisted_floor_id]
            node_ids_for_floor = {n.get("id") for n in nodes_for_floor}
            edges_for_floor = [
                e for e in edges
                if e.get("from_node_id") in node_ids_for_floor and e.get("to_node_id") in node_ids_for_floor
            ]
            pois_for_floor = [p for p in pois if p.get("floor_id") == persisted_floor_id]

            print("[6/6] Test summary")
            print("=" * 72)
            print(f"Building UUID (created):  {building_id}")
            print(f"Floor UUID (created):     {floor_id}")
            print(f"Building UUID (persist):  {persist_result.get('building_id')}")
            print(f"Floor UUID (persist):     {persisted_floor_id}")
            print("-")
            print(f"Routing nodes persisted:  {len(nodes_for_floor)}")
            print(f"Routing edges persisted:  {len(edges_for_floor)}")
            print(f"POIs persisted:           {len(pois_for_floor)}")
            print("-")
            print(f"Persist API status:       {persist_result.get('status')}")
            print(f"Persist raw counts:       nodes={persist_result.get('routing_nodes_inserted')}, "
                  f"edges={persist_result.get('routing_edges_inserted')}, "
                  f"pois={persist_result.get('pois_inserted')}, "
                  f"edges_skipped={persist_result.get('routing_edges_skipped')}")
            print("-")

            matching_buildings = [b for b in buildings if b.get("id") == persist_result.get("building_id")]
            matching_floors = [fl for fl in floors if fl.get("id") == persisted_floor_id]

            print(f"Building stored check:    {'OK' if matching_buildings else 'FAILED'}")
            print(f"Floor stored check:       {'OK' if matching_floors else 'FAILED'}")
            if matching_floors:
                fg = matching_floors[0].get("floor_geojson")
                print(f"Floor JSONB check:        {'OK' if isinstance(fg, dict) else 'FAILED'}")

            geom_ok = bool(matching_buildings and matching_buildings[0].get("geometry") is not None)
            print(f"Building WKT/geometry:    {'OK' if geom_ok else 'FAILED'}")
            print("=" * 72)

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
