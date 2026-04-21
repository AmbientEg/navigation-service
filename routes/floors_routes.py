from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from database import get_db_session
from models.buildings import Building
from models.floors import Floor

router = APIRouter()


def _serialize_floor(floor: Floor) -> dict:
    floor_geojson = getattr(floor, "floor_geojson", None)
    if not isinstance(floor_geojson, dict):
        floor_geojson = {"type": "FeatureCollection", "features": []}

    level_number = getattr(floor, "level_number", 0)
    try:
        level_number = int(level_number)
    except Exception:
        level_number = 0

    height_meters = getattr(floor, "height_meters", 0.0)
    try:
        height_meters = float(height_meters)
    except Exception:
        height_meters = 0.0

    return {
        "id": str(floor.id),
        "building_id": str(floor.building_id),
        "level_number": level_number,
        "name": str(getattr(floor, "name", "")),
        "height_meters": height_meters,
        "floor_geojson": floor_geojson,
    }


class FloorCreateRequest(BaseModel):
    building_id: str
    level_number: int
    name: str = Field(..., min_length=1, max_length=255)
    height_meters: float = Field(..., gt=0)
    floor_geojson: dict

    @field_validator("floor_geojson")
    @classmethod
    def validate_floor_geojson(cls, value: dict) -> dict:
        if not isinstance(value, dict):
            raise ValueError("floor_geojson must be an object")
        if value.get("type") != "FeatureCollection":
            raise ValueError("floor_geojson.type must be FeatureCollection")
        features = value.get("features")
        if not isinstance(features, list):
            raise ValueError("floor_geojson.features must be a list")
        return value


class FloorGeoJSONUpdateRequest(BaseModel):
    floor_geojson: dict

    @field_validator("floor_geojson")
    @classmethod
    def validate_floor_geojson(cls, value: dict) -> dict:
        if not isinstance(value, dict):
            raise ValueError("floor_geojson must be an object")
        if value.get("type") != "FeatureCollection":
            raise ValueError("floor_geojson.type must be FeatureCollection")
        features = value.get("features")
        if not isinstance(features, list):
            raise ValueError("floor_geojson.features must be a list")
        return value


@router.post("/create")
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
    return _serialize_floor(floor)


@router.put("/update/{floor_id}")
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
    return _serialize_floor(floor)


@router.get("/get/{floor_id}/map")
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
