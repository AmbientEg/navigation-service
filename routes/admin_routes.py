import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import WKTElement

from database import get_db_session
from models.buildings import Building
from models.floors import Floor
from models.node_types import NodeType
from models.edge_types import EdgeType
from models.routing_nodes import RoutingNode
from models.routing_edges import RoutingEdge
from models.poi import POI
from services.graph_persistence_service import persist_pipeline_output
from .admin_auth import require_admin


router = APIRouter(dependencies=[Depends(require_admin)])


# ---------- Schemas ----------
class BuildingCreate(BaseModel):
    name: str
    description: Optional[str] = None
    floors_count: int = 0
    geometry_wkt: str = Field(..., description="WKT polygon")


class FloorCreate(BaseModel):
    building_id: str
    level_number: int
    name: str
    height_meters: float
    floor_geojson: dict[str, Any]


class NodeTypeCreate(BaseModel):
    code: str
    description: Optional[str] = None


class EdgeTypeCreate(BaseModel):
    code: str
    is_accessible: bool = True
    description: Optional[str] = None


class RoutingNodeCreate(BaseModel):
    floor_id: str
    node_type_id: str
    geometry_wkt: str = Field(..., description="WKT point")
    name: Optional[str] = None


class RoutingEdgeCreate(BaseModel):
    from_node_id: str
    to_node_id: str
    edge_type_id: str
    distance: float


class POICreate(BaseModel):
    floor_id: str
    name: str
    type: str
    geometry_wkt: str = Field(..., description="WKT point")
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersistGraphRequest(BaseModel):
    graph_geojson_path: str = "navigation_graph_verified.geojson"
    floor_geojson_path: str = "floor3_centerlines.geojson"
    building_name: str = "Default Building"
    building_description: Optional[str] = "Auto-generated from pipeline"
    floor_level: int = 3
    floor_name: str = "3rd Floor"
    floor_height: float = 3.2
    clear_existing_floor_data: bool = True


# ---------- Buildings ----------
@router.get("/buildings")
async def list_buildings(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(Building))
    return result.scalars().all()


@router.post("/buildings")
async def create_building(payload: BuildingCreate, db: AsyncSession = Depends(get_db_session)):
    building = Building(
        name=payload.name,
        description=payload.description,
        floors_count=payload.floors_count,
        geometry=WKTElement(payload.geometry_wkt, srid=4326),
    )
    db.add(building)
    await db.commit()
    await db.refresh(building)
    return building


# ---------- Floors ----------
@router.get("/floors")
async def list_floors(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(Floor))
    return result.scalars().all()


@router.post("/floors")
async def create_floor(payload: FloorCreate, db: AsyncSession = Depends(get_db_session)):
    try:
        building_id = uuid.UUID(payload.building_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid building_id") from e

    floor = Floor(
        building_id=building_id,
        level_number=payload.level_number,
        name=payload.name,
        height_meters=payload.height_meters,
        floor_geojson=payload.floor_geojson,
    )
    db.add(floor)
    await db.commit()
    await db.refresh(floor)
    return floor


# ---------- Node Types ----------
@router.get("/node-types")
async def list_node_types(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(NodeType))
    return result.scalars().all()


@router.post("/node-types")
async def create_node_type(payload: NodeTypeCreate, db: AsyncSession = Depends(get_db_session)):
    row = NodeType(code=payload.code, description=payload.description)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- Edge Types ----------
@router.get("/edge-types")
async def list_edge_types(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(EdgeType))
    return result.scalars().all()


@router.post("/edge-types")
async def create_edge_type(payload: EdgeTypeCreate, db: AsyncSession = Depends(get_db_session)):
    row = EdgeType(
        code=payload.code,
        is_accessible=payload.is_accessible,
        description=payload.description,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- Routing Nodes ----------
@router.get("/routing-nodes")
async def list_routing_nodes(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(RoutingNode))
    return result.scalars().all()


@router.post("/routing-nodes")
async def create_routing_node(payload: RoutingNodeCreate, db: AsyncSession = Depends(get_db_session)):
    try:
        floor_id = uuid.UUID(payload.floor_id)
        node_type_id = uuid.UUID(payload.node_type_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid UUID in floor_id/node_type_id") from e

    row = RoutingNode(
        floor_id=floor_id,
        node_type_id=node_type_id,
        geometry=WKTElement(payload.geometry_wkt, srid=4326),
        name=payload.name,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- Routing Edges ----------
@router.get("/routing-edges")
async def list_routing_edges(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(RoutingEdge))
    return result.scalars().all()


@router.post("/routing-edges")
async def create_routing_edge(payload: RoutingEdgeCreate, db: AsyncSession = Depends(get_db_session)):
    try:
        from_node_id = uuid.UUID(payload.from_node_id)
        to_node_id = uuid.UUID(payload.to_node_id)
        edge_type_id = uuid.UUID(payload.edge_type_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid UUID in edge payload") from e

    if payload.distance <= 0:
        raise HTTPException(status_code=400, detail="distance must be > 0")

    row = RoutingEdge(
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        edge_type_id=edge_type_id,
        distance=payload.distance,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- POIs ----------
@router.get("/pois")
async def list_pois(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(POI))
    return result.scalars().all()


@router.post("/pois")
async def create_poi(payload: POICreate, db: AsyncSession = Depends(get_db_session)):
    try:
        floor_id = uuid.UUID(payload.floor_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid floor_id") from e

    row = POI(
        floor_id=floor_id,
        name=payload.name,
        type=payload.type,
        geometry=WKTElement(payload.geometry_wkt, srid=4326),
        extra_data=payload.metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- Persist graph ----------
@router.post("/graph/persist")
async def persist_graph_to_db(
    payload: PersistGraphRequest,
    db: AsyncSession = Depends(get_db_session),
):
    result = await persist_pipeline_output(
        db=db,
        graph_geojson_path=payload.graph_geojson_path,
        floor_geojson_path=payload.floor_geojson_path,
        building_name=payload.building_name,
        building_description=payload.building_description,
        floor_level=payload.floor_level,
        floor_name=payload.floor_name,
        floor_height=payload.floor_height,
        clear_existing_floor_data=payload.clear_existing_floor_data,
    )
    return result
