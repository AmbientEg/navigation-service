import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import db_manager
from services.graph_persistence_service import persist_pipeline_output


def _resolve_path(default_filename: str) -> str:
    cwd_path = Path.cwd() / default_filename
    if cwd_path.exists():
        return str(cwd_path)

    pipeline_path = Path(__file__).resolve().parent / default_filename
    return str(pipeline_path)


async def main_async():
    await db_manager.initialize()
    try:
        graph_path = os.getenv("PIPELINE_GRAPH_GEOJSON", _resolve_path("navigation_graph_verified.geojson"))
        if not Path(graph_path).exists():
            graph_path = _resolve_path("navigation_graph_export.geojson")

        floor_path = os.getenv("PIPELINE_FLOOR_GEOJSON", _resolve_path("floor3_centerlines.geojson"))

        building_name = os.getenv("PIPELINE_BUILDING_NAME", "Default Building")
        building_description = os.getenv("PIPELINE_BUILDING_DESCRIPTION", "Auto-generated from pipeline")
        floor_level = int(os.getenv("PIPELINE_FLOOR_LEVEL", "3"))
        floor_name = os.getenv("PIPELINE_FLOOR_NAME", "3rd Floor")
        floor_height = float(os.getenv("PIPELINE_FLOOR_HEIGHT", "3.2"))

        async with db_manager.get_session() as db:
            result = await persist_pipeline_output(
                db=db,
                graph_geojson_path=graph_path,
                floor_geojson_path=floor_path,
                building_name=building_name,
                building_description=building_description,
                floor_level=floor_level,
                floor_name=floor_name,
                floor_height=floor_height,
                clear_existing_floor_data=True,
            )

        print("Graph persistence completed:")
        for k, v in result.items():
            print(f"  {k}: {v}")

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main_async())
