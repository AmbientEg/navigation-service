from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_AsText
import uuid

from database import get_db_session
from models.buildings import Building
from models.floors import Floor

router = APIRouter()


class BuildingCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    floors_count: int = Field(default=0, ge=0)
    geometry_wkt: str = Field(..., description="Building footprint polygon as WKT")


def _serialize_building_row(row) -> dict:
    """Convert a SQLAlchemy result row into a JSON-safe building payload."""
    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "floors_count": row.floors_count,
        "geometry_wkt": row.geometry_wkt,
    }


async def _get_building_row_or_404(db: AsyncSession, building_uuid: uuid.UUID):
    row = (
        await db.execute(
            select(
                Building.id,
                Building.name,
                Building.description,
                Building.floors_count,
                ST_AsText(Building.geometry).label("geometry_wkt"),
            ).where(Building.id == building_uuid)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Building not found")
    return row


@router.get("")
async def list_buildings(
    db: AsyncSession = Depends(get_db_session)
):
    """Return all buildings with geometry as WKT string."""
    rows = (
        await db.execute(
            select(
                Building.id,
                Building.name,
                Building.description,
                Building.floors_count,
                ST_AsText(Building.geometry).label("geometry_wkt"),
            ).order_by(Building.name.asc())
        )
    ).all()
    return [_serialize_building_row(row) for row in rows]


@router.post("")
async def create_building(
    request: BuildingCreateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Create a building and return the created entity."""
    geometry_wkt = request.geometry_wkt.strip()
    if not geometry_wkt.upper().startswith("POLYGON"):
        raise HTTPException(status_code=400, detail="geometry_wkt must be a POLYGON WKT")

    building = Building(
        name=request.name,
        description=request.description,
        floors_count=request.floors_count,
        geometry=WKTElement(geometry_wkt, srid=4326),
    )
    db.add(building)
    await db.commit()
    created_row = await _get_building_row_or_404(db, building.id)
    return _serialize_building_row(created_row)


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
    
    building_row = await _get_building_row_or_404(db, building_uuid)
    return _serialize_building_row(building_row)


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
