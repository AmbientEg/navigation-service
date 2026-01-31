from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db_session
from models.poi import POI

router = APIRouter()

@router.get("/floor/{floor_id}")
async def get_floor_pois(
    floor_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(POI).where(POI.floor_id == floor_id)
    )
    return result.scalars().all()
