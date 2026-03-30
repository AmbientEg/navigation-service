from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from database import get_db_session
from models.buildings import Building
from models.floors import Floor

router = APIRouter()


class FloorCreateRequest(BaseModel):
    building_id: str
    level_number: int
    name: str = Field(..., min_length=1, max_length=255)
    height_meters: float = Field(..., gt=0)
    floor_geojson: dict


class FloorGeoJSONUpdateRequest(BaseModel):
    floor_geojson: dict


@router.post("")
async def create_floor(
    request: FloorCreateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Create a floor and store floor GeoJSON as source of truth."""
    try:
        building_uuid = uuid.UUID(request.building_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid building ID format")

    building = await db.get(Building, building_uuid)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    floor = Floor(
        building_id=building_uuid,
        level_number=request.level_number,
        name=request.name,
        height_meters=request.height_meters,
        floor_geojson=request.floor_geojson,
    )
    db.add(floor)
    building.floors_count = (building.floors_count or 0) + 1
    await db.commit()
    await db.refresh(floor)
    return floor


@router.put("/{floor_id}")
async def update_floor_geojson(
    floor_id: str,
    request: FloorGeoJSONUpdateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Replace floor GeoJSON map data without rebuilding graph automatically."""
    try:
        floor_uuid = uuid.UUID(floor_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid floor ID format")

    floor = await db.get(Floor, floor_uuid)
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    floor.floor_geojson = request.floor_geojson
    await db.commit()
    await db.refresh(floor)
    return floor


@router.get("/{floor_id}/map")
async def get_floor_map(
    floor_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get floor map as GeoJSON FeatureCollection.
    
    This endpoint returns the indoor map data in GeoJSON format,
    ready to be consumed by Mapbox or other mapping libraries.
    
    Returns:
        GeoJSON FeatureCollection with floor features
    """
    try:
        floor_uuid = uuid.UUID(floor_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid floor ID format")
    
    floor = await db.get(Floor, floor_uuid)
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    # Return valid GeoJSON FeatureCollection for Mapbox
    if not floor.floor_geojson:
        return {
            "type": "FeatureCollection",
            "features": []
        }
    
    # Ensure the response is a proper FeatureCollection
    geojson = floor.floor_geojson
    if isinstance(geojson, dict):
        if geojson.get("type") == "FeatureCollection":
            return geojson
        else:
            # Wrap in FeatureCollection if needed
            return {
                "type": "FeatureCollection",
                "features": geojson.get("features", [])
            }
    
    return {
        "type": "FeatureCollection",
        "features": []
    }
