from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from database import get_db_session
from models.poi import POI
from services import routing_service

router = APIRouter()

# ---------- Schemas ----------

class RouteFrom(BaseModel):
    floorId: str = Field(..., description="UUID of the starting floor")
    lat: float = Field(..., description="Latitude of starting position")
    lng: float = Field(..., description="Longitude of starting position")


class RouteTo(BaseModel):
    poiId: str = Field(..., description="UUID of destination POI")


class RouteOptions(BaseModel):
    accessible: bool = Field(default=True, description="Whether to use accessible routes only")


class RouteRequest(BaseModel):
    from_: RouteFrom = Field(..., alias="from")
    to: RouteTo
    options: RouteOptions = Field(default_factory=RouteOptions)

    class Config:
        populate_by_name = True


class RouteFloorPath(BaseModel):
    floorId: str
    path: list[list[float]]  # [[lng, lat], [lng, lat]]


class RouteResponse(BaseModel):
    floors: list[RouteFloorPath]
    distance: float
    steps: list[str]


# POST /api/navigation/route
@router.post("/route", response_model=RouteResponse)
async def calculate_route(
    request: RouteRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Calculate navigation route from a coordinate to a POI.
    
    - **from**: Starting position with floor ID and coordinates
    - **to**: Destination POI ID
    - **options**: Routing options (accessible routes, etc.)
    
    Returns the route path grouped by floors, total distance, and navigation steps.
    """
    try:
        # Validate UUIDs
        from_floor_id = uuid.UUID(request.from_.floorId)
        to_poi_id = uuid.UUID(request.to.poiId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    # Validate destination POI exists
    poi = await db.get(POI, to_poi_id)
    if not poi:
        raise HTTPException(status_code=404, detail="Destination POI not found")
    
    try:
        # Calculate route using routing service
        route_data = await routing_service.calculate_route(
            db=db,
            from_floor_id=from_floor_id,
            from_lat=request.from_.lat,
            from_lng=request.from_.lng,
            to_poi_id=to_poi_id,
            accessible=request.options.accessible
        )
        
        return RouteResponse(**route_data)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route calculation failed: {str(e)}")
