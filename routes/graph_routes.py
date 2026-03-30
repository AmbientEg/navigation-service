import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from services.graph_workflow_service import (
    build_graph_preview_for_building,
    confirm_graph_preview,
    rollback_to_previous_graph_version,
)

router = APIRouter()


@router.post("/rebuild/{building_id}")
async def rebuild_graph_preview(
    building_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Rebuild a stitched multi-floor graph from floor GeoJSON and return preview JSON."""
    try:
        building_uuid = uuid.UUID(building_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid building ID format")

    try:
        preview = await build_graph_preview_for_building(db, building_uuid)
        return {"status": "preview", **preview}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph rebuild failed: {exc}")


@router.post("/confirm/{building_id}")
async def confirm_graph(
    building_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Confirm current graph snapshot by rebuilding from DB and persisting as active version."""
    try:
        building_uuid = uuid.UUID(building_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid building ID format")

    try:
        preview = await build_graph_preview_for_building(db, building_uuid)
        persisted = await confirm_graph_preview(db, building_uuid, preview)
        return {
            "status": "confirmed",
            **persisted,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph confirmation failed: {exc}")


@router.post("/rollback/{building_id}")
async def rollback_graph(
    building_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Quick rollback: mark previous graph version active for the building."""
    try:
        building_uuid = uuid.UUID(building_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid building ID format")

    try:
        rollback = await rollback_to_previous_graph_version(db, building_uuid)
        return {"status": "rolled_back", **rollback}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph rollback failed: {exc}")
