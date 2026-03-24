import json
import logging
from pathlib import Path
from typing import Any

from geoalchemy2 import WKTElement
from shapely.geometry import shape, Polygon
from shapely.ops import unary_union
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.buildings import Building
from models.floors import Floor
from models.node_types import NodeType
from models.edge_types import EdgeType
from models.routing_nodes import RoutingNode
from models.routing_edges import RoutingEdge
from models.poi import POI
from services.crs_service import normalize_point_for_db, validate_wgs84_coordinates, looks_like_utm

logger = logging.getLogger(__name__)


DEFAULT_NODE_TYPES = [
    ("corridor", "Corridor centerline node"),
    ("junction", "Corridor junction / decision point"),
    ("door", "Door node"),
    ("room", "Room anchor node"),
    ("stairs", "Stair connector"),
    ("elevator", "Elevator connector"),
    ("entrance", "Entrance connector"),
    ("unknown", "Fallback node type"),
]

DEFAULT_EDGE_TYPES = [
    ("corridor", True, "Corridor walk edge"),
    ("door", True, "Door connector edge"),
    ("room_connection", True, "Room to door connector"),
    ("vertical", False, "Vertical movement connector"),
    ("stairs", False, "Stairs connector"),
    ("elevator", True, "Elevator connector"),
    ("unknown", True, "Fallback edge type"),
]


def _load_json(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _point_wkt_from_xy(x: float, y: float) -> str:
    """
    Create a WKT POINT string from x, y coordinates.
    
    Coordinates should already be normalized to WGS84 before calling this function.
    See normalize_point_for_db() for CRS normalization.
    """
    return f"POINT({x} {y})"


def _build_building_footprint_wkt(floor_geojson: dict[str, Any]) -> str:
    polygons = []
    for feature in floor_geojson.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        geom = shape(geometry)
        if geom.geom_type in {"Polygon", "MultiPolygon"}:
            polygons.append(geom)

    if polygons:
        merged = unary_union(polygons)
        if merged.geom_type == "Polygon":
            hull = merged
        else:
            hull = merged.convex_hull
        return hull.wkt

    all_points = []
    for feature in floor_geojson.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        geom = shape(geometry)
        minx, miny, maxx, maxy = geom.bounds
        all_points.extend([(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)])

    if len(all_points) >= 3:
        return Polygon(all_points).convex_hull.wkt

    return "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"


async def _get_or_create_building(
    db: AsyncSession,
    building_name: str,
    building_description: str | None,
    floor_geojson: dict[str, Any],
) -> Building:
    existing = await db.execute(
        select(Building)
        .where(Building.name == building_name)
        .order_by(Building.updated_at.desc())
    )
    building = existing.scalars().first()

    geometry_wkt = _build_building_footprint_wkt(floor_geojson)

    if building:
        building.description = building_description
        building.geometry = WKTElement(geometry_wkt, srid=4326)
        await db.flush()
        return building

    building = Building(
        name=building_name,
        description=building_description,
        floors_count=0,
        geometry=WKTElement(geometry_wkt, srid=4326),
    )
    db.add(building)
    await db.flush()
    return building


async def _get_or_create_floor(
    db: AsyncSession,
    building_id,
    floor_level: int,
    floor_name: str,
    floor_height: float,
    floor_geojson: dict[str, Any],
) -> Floor:
    existing = await db.execute(
        select(Floor).where(
            Floor.building_id == building_id,
            Floor.level_number == floor_level,
        )
    )
    floor = existing.scalar_one_or_none()

    if floor:
        floor.name = floor_name
        floor.height_meters = floor_height
        floor.floor_geojson = floor_geojson
        await db.flush()
        return floor

    floor = Floor(
        building_id=building_id,
        level_number=floor_level,
        name=floor_name,
        height_meters=floor_height,
        floor_geojson=floor_geojson,
    )
    db.add(floor)
    await db.flush()
    return floor


async def _seed_node_types(db: AsyncSession) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for code, description in DEFAULT_NODE_TYPES:
        res = await db.execute(select(NodeType).where(NodeType.code == code))
        row = res.scalar_one_or_none()
        if row is None:
            row = NodeType(code=code, description=description)
            db.add(row)
            await db.flush()
        mapping[code] = row.id
    return mapping


async def _seed_edge_types(db: AsyncSession) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for code, is_accessible, description in DEFAULT_EDGE_TYPES:
        res = await db.execute(select(EdgeType).where(EdgeType.code == code))
        row = res.scalar_one_or_none()
        if row is None:
            row = EdgeType(code=code, is_accessible=is_accessible, description=description)
            db.add(row)
            await db.flush()
        mapping[code] = row.id
    return mapping


async def _clear_floor_graph_data(db: AsyncSession, floor_id):
    node_id_subq = select(RoutingNode.id).where(RoutingNode.floor_id == floor_id)

    await db.execute(
        delete(RoutingEdge).where(
            or_(
                RoutingEdge.from_node_id.in_(node_id_subq),
                RoutingEdge.to_node_id.in_(node_id_subq),
            )
        )
    )
    await db.execute(delete(RoutingNode).where(RoutingNode.floor_id == floor_id))
    await db.execute(delete(POI).where(POI.floor_id == floor_id))


def _extract_graph_features(graph_geojson: dict[str, Any]):
    nodes = []
    edges = []
    for feature in graph_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        if geometry.get("type") == "Point":
            nodes.append((geometry, props))
        elif geometry.get("type") == "LineString":
            edges.append((geometry, props))
    return nodes, edges


def _poi_geom_from_feature(geom):
    gtype = geom.geom_type
    if gtype in {"Polygon", "MultiPolygon"}:
        return geom.centroid
    if gtype in {"LineString", "MultiLineString"}:
        return geom.interpolate(0.5, normalized=True)
    return geom


def _normalize_space_type(raw_space_type: str, geom_type: str) -> str:
    """Normalize GeoJSON space type for DB storage while preserving source type."""
    st = (raw_space_type or "").lower().strip()
    return st or "poi"


def _is_truthy_poi(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return False


def _is_poi_candidate(space_type: str, geom_type: str, props: dict[str, Any]) -> bool:
    # Persist only explicit POIs from source map.
    return _is_truthy_poi(props.get("poi"))


async def persist_pipeline_output(
    db: AsyncSession,
    graph_geojson_path: str,
    floor_geojson_path: str,
    building_name: str,
    building_description: str | None,
    floor_level: int,
    floor_name: str,
    floor_height: float,
    clear_existing_floor_data: bool = True,
) -> dict[str, Any]:
    """Persist step2/step3 graph and floor POIs into DB tables."""
    floor_geojson = _load_json(floor_geojson_path)
    graph_geojson = _load_json(graph_geojson_path)

    building = await _get_or_create_building(
        db=db,
        building_name=building_name,
        building_description=building_description,
        floor_geojson=floor_geojson,
    )

    floor = await _get_or_create_floor(
        db=db,
        building_id=building.id,
        floor_level=floor_level,
        floor_name=floor_name,
        floor_height=floor_height,
        floor_geojson=floor_geojson,
    )

    node_type_map = await _seed_node_types(db)
    edge_type_map = await _seed_edge_types(db)

    if clear_existing_floor_data:
        await _clear_floor_graph_data(db, floor.id)

    graph_nodes, graph_edges = _extract_graph_features(graph_geojson)

    graph_node_id_to_db_id = {}
    dedupe_by_coord = {}

    # 1) ROUTING_NODES
    for geometry, props in graph_nodes:
        coords = geometry.get("coordinates", [None, None])
        if coords[0] is None or coords[1] is None:
            logger.warning(f"Skipping node with missing coordinates: {props}")
            continue

        x, y = float(coords[0]), float(coords[1])
        
        # ===== CRS NORMALIZATION: Detect and convert to WGS84 if needed =====
        # Pipeline typically outputs UTM coordinates (x > 180 or |y| > 90 suggests UTM).
        # DB stores all geometries in WGS84 (EPSG:4326).
        source_crs = "UTM" if looks_like_utm(x, y) else "WGS84"
        try:
            x_normalized, y_normalized = normalize_point_for_db(
                x, y,
                source_crs=source_crs,
                target_crs="WGS84"
            )
        except ValueError as e:
            logger.error(f"Failed to normalize node coordinates ({x}, {y}): {e}. Skipping node.")
            continue
        
        # Validate final WGS84 coordinates
        if not validate_wgs84_coordinates(x_normalized, y_normalized):
            logger.error(
                f"Node coordinates {(x_normalized, y_normalized)} outside WGS84 range after normalization. Skipping."
            )
            continue
        
        # ===== Deduplication by rounded coordinates =====
        key = (floor.id, round(x_normalized, 8), round(y_normalized, 8))

        if key in dedupe_by_coord:
            db_node = dedupe_by_coord[key]
        else:
            node_type_code = (props.get("node_type") or "unknown").lower()
            node_type_id = node_type_map.get(node_type_code, node_type_map["unknown"])

            # Create node with normalized WGS84 coordinates and explicit SRID=4326
            db_node = RoutingNode(
                floor_id=floor.id,
                node_type_id=node_type_id,
                geometry=WKTElement(_point_wkt_from_xy(x_normalized, y_normalized), srid=4326),
                name=props.get("name"),
            )
            db.add(db_node)
            await db.flush()
            dedupe_by_coord[key] = db_node

        graph_node_id = props.get("node_id")
        if graph_node_id is not None:
            graph_node_id_to_db_id[graph_node_id] = db_node.id

    # 2) ROUTING_EDGES
    inserted_edges = 0
    skipped_edges = 0
    for _, props in graph_edges:
        source = props.get("source")
        target = props.get("target")
        weight = props.get("weight")

        from_node_id = graph_node_id_to_db_id.get(source)
        to_node_id = graph_node_id_to_db_id.get(target)

        if from_node_id is None or to_node_id is None or from_node_id == to_node_id:
            skipped_edges += 1
            continue

        if weight is None or float(weight) <= 0:
            skipped_edges += 1
            continue

        edge_type_code = (props.get("edge_type") or "unknown").lower()
        if props.get("is_vertical"):
            edge_type_code = "vertical"

        edge_type_id = edge_type_map.get(edge_type_code, edge_type_map["unknown"])

        db.add(
            RoutingEdge(
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                edge_type_id=edge_type_id,
                distance=float(weight),
            )
        )
        inserted_edges += 1

    # 3) POIS (only features explicitly flagged with poi=true/truthy)
    inserted_pois = 0

    for idx, feature in enumerate(floor_geojson.get("features", []), start=1):
        props = feature.get("properties", {})
        geometry = feature.get("geometry")
        if not geometry:
            continue

        geom_type = geometry.get("type", "")
        space_type = (props.get("space_type") or "").lower()
        if not _is_poi_candidate(space_type, geom_type, props):
            continue

        geom_obj = shape(geometry)
        poi_point = _poi_geom_from_feature(geom_obj)
        normalized_type = _normalize_space_type(space_type, geom_obj.geom_type)
        poi_name = props.get("name") or props.get("label") or f"{normalized_type}_{idx}"

        # ===== CRS NORMALIZATION: Detect and convert POI coordinates to WGS84 =====
        # POI geometry is extracted as a centroid or interpolated point.
        # Ensure it's normalized to WGS84 before persisting.
        x_poi, y_poi = poi_point.x, poi_point.y
        source_crs = "UTM" if looks_like_utm(x_poi, y_poi) else "WGS84"
        
        try:
            x_normalized, y_normalized = normalize_point_for_db(
                x_poi, y_poi,
                source_crs=source_crs,
                target_crs="WGS84"
            )
        except ValueError as e:
            logger.error(f"Failed to normalize POI '{poi_name}' coordinates ({x_poi}, {y_poi}): {e}. Skipping POI.")
            continue
        
        # Validate final WGS84 coordinates
        if not validate_wgs84_coordinates(x_normalized, y_normalized):
            logger.error(
                f"POI '{poi_name}' coordinates {(x_normalized, y_normalized)} outside WGS84 range after normalization. Skipping."
            )
            continue
        
        # Create POI with normalized WGS84 coordinates and explicit SRID=4326
        poi_point_normalized = type(poi_point)(x_normalized, y_normalized)
        db.add(
            POI(
                floor_id=floor.id,
                name=poi_name,
                type=normalized_type,
                geometry=WKTElement(poi_point_normalized.wkt, srid=4326),
                extra_data=props,
            )
        )
        inserted_pois += 1

    # Update building floors count
    floors_count_result = await db.execute(select(Floor).where(Floor.building_id == building.id))
    building.floors_count = len(floors_count_result.scalars().all())

    await db.commit()

    return {
        "status": "ok",
        "building_id": str(building.id),
        "floor_id": str(floor.id),
        "routing_nodes_inserted": len(dedupe_by_coord),
        "routing_edges_inserted": inserted_edges,
        "routing_edges_skipped": skipped_edges,
        "pois_inserted": inserted_pois,
        "graph_geojson_path": graph_geojson_path,
        "floor_geojson_path": floor_geojson_path,
    }
