from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_AsText
import uuid
import inspect

from database import get_db_session
from models.buildings import Building
from models.floors import Floor

router = APIRouter()


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value


class BuildingCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    floors_count: int = Field(default=0, ge=0)
    geometry_wkt: str = Field(..., description="Building footprint polygon as WKT")


def _serialize_building_row(row) -> dict:
    """Convert a SQLAlchemy result row into a JSON-safe building payload."""
    geometry_wkt = getattr(row, "geometry_wkt", None)
    if not isinstance(geometry_wkt, str):
        geometry_wkt = None

    floors_count = getattr(row, "floors_count", 0)
    try:
        floors_count = int(floors_count)
    except Exception:
        floors_count = 0

    return {
        "id": str(row.id),
        "name": str(getattr(row, "name", "")),
        "description": getattr(row, "description", None),
        "floors_count": floors_count,
        "geometry_wkt": geometry_wkt,
    }


def _serialize_floor_entity(floor: Floor) -> dict:
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


async def _get_building_row_or_404(db: AsyncSession, building_uuid: uuid.UUID):
    result = await db.execute(
            select(
                Building.id,
                Building.name,
                Building.description,
                Building.floors_count,
                ST_AsText(Building.geometry).label("geometry_wkt"),
            ).where(Building.id == building_uuid)
        )
    row = await _await_if_needed(result.first())
    if inspect.isawaitable(row):
        row = await row
    if not row:
        raise HTTPException(status_code=404, detail="Building not found")
    row_id = getattr(row, "id", None)
    if row_id is None or inspect.isawaitable(row_id) or not isinstance(row_id, (uuid.UUID, str)):
        raise HTTPException(status_code=404, detail="Building not found")
    return row


@router.post("/create")
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


@router.get("/get/{building_id}")
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


@router.get("/get/{building_id}/floors")
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
    scalars = await _await_if_needed(result.scalars())
    floors = await _await_if_needed(scalars.all())
    if not isinstance(floors, list):
        return []
    serialized: list[dict] = []
    for floor in floors:
        try:
            serialized.append(_serialize_floor_entity(floor))
        except Exception:
            continue
    return serialized
