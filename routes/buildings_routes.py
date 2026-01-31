from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from database import get_db_session
from models.buildings import Building
from models.floors import Floor

router = APIRouter()


@router.get("/{building_id}")
async def get_building(
    building_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get building information by ID.
    
    Returns building details including name, description, floor count, and geometry.
    """
    try:
        building_uuid = uuid.UUID(building_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid building ID format")
    
    building = await db.get(Building, building_uuid)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    return building


@router.get("/{building_id}/floors")
async def get_building_floors(
    building_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all floors for a specific building.
    
    Returns a list of floors with their level numbers, names, and GeoJSON data.
    """
    try:
        building_uuid = uuid.UUID(building_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid building ID format")
    
    # Verify building exists
    building = await db.get(Building, building_uuid)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    
    result = await db.execute(
        select(Floor).where(Floor.building_id == building_uuid)
    )
    return result.scalars().all()
