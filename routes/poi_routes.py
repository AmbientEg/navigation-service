"""
POI CRUD routes - list by floor, update, and delete endpoints.
Kept separate to avoid modifying admin_routes.py.
"""
import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import WKTElement

from database import get_db_session
from models.poi import POI


router = APIRouter()


def _serialize_poi(row: POI) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "floor_id": str(row.floor_id),
        "name": row.name,
        "type": row.type,
        "geometry": None,
        "extra_data": row.extra_data or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class POIUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    geometry_wkt: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@router.get("/floor/{floor_id}")
async def get_pois_by_floor(floor_id: str, db: AsyncSession = Depends(get_db_session)):
    try:
        floor_uuid = uuid.UUID(floor_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid floor_id") from e

    result = await db.execute(select(POI).where(POI.floor_id == floor_uuid))
    rows = result.scalars().all()
    return [_serialize_poi(row) for row in rows]


@router.put("/{poi_id}")
async def update_poi(poi_id: str, payload: POIUpdate, db: AsyncSession = Depends(get_db_session)):
    try:
        poi_uuid = uuid.UUID(poi_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid poi_id") from e

    result = await db.execute(select(POI).where(POI.id == poi_uuid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="POI not found")

    if payload.name is not None:
        row.name = payload.name
    if payload.type is not None:
        row.type = payload.type
    if payload.geometry_wkt is not None:
        row.geometry = WKTElement(payload.geometry_wkt, srid=4326)
    if payload.metadata is not None:
        row.extra_data = payload.metadata

    await db.commit()
    await db.refresh(row)
    return _serialize_poi(row)


@router.delete("/{poi_id}")
async def delete_poi(poi_id: str, db: AsyncSession = Depends(get_db_session)):
    try:
        poi_uuid = uuid.UUID(poi_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid poi_id") from e

    result = await db.execute(select(POI).where(POI.id == poi_uuid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="POI not found")

    await db.delete(row)
    await db.commit()
    return {"success": True, "id": poi_id}
