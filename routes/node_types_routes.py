from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db_session
from models.node_types import NodeType

router = APIRouter()

@router.get("/")
async def list_node_types(
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(select(NodeType))
    return result.scalars().all()
