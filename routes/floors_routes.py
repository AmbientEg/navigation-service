from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from database import get_db_session
from models.floors import Floor

router = APIRouter()


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
