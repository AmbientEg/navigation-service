import math
import uuid
from collections import defaultdict

from geoalchemy2 import WKTElement
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.buildings import Building
from models.edge_types import EdgeType
from models.floors import Floor
from models.navigation_graph_versions import NavigationGraphVersion
from models.node_types import NodeType
from models.routing_edges import RoutingEdge
from models.routing_nodes import RoutingNode
from pipeline.step2_construct_graph import build_navigation_graph


VERTICAL_NAME_HINTS = {"stair", "stairs", "elevator", "lift", "entrance", "exit"}
DEFAULT_VERTICAL_TRAVEL_METERS = 3.0


def _safe_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _distance_meters(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    # Fast local approximation good enough for indoor stitching.
    avg_lat_rad = math.radians((lat1 + lat2) / 2.0)
    meters_per_deg_lat = 111_132.0
    meters_per_deg_lng = 111_320.0 * math.cos(avg_lat_rad)
    dx = (lng2 - lng1) * meters_per_deg_lng
    dy = (lat2 - lat1) * meters_per_deg_lat
    return math.sqrt(dx * dx + dy * dy)


def _extract_coordinates(node, attrs: dict) -> tuple[float, float] | None:
    if isinstance(node, (tuple, list)) and len(node) >= 2:
        return float(node[0]), float(node[1])
    x = attrs.get("x")
    y = attrs.get("y")
    if x is not None and y is not None:
        return float(x), float(y)
    return None


def _is_vertical_candidate(node: dict) -> bool:
    node_type = (node.get("node_type") or "").lower()
    name = (node.get("name") or "").lower()
    if node_type in VERTICAL_NAME_HINTS:
        return True
    return any(hint in name for hint in VERTICAL_NAME_HINTS)


def _preview_nodes_edges_for_floor(floor: Floor, floor_graph) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []
    edges: list[dict] = []
    node_map: dict[object, str] = {}

    node_index = 1
    for raw_node, attrs in floor_graph.nodes(data=True):
        coords = _extract_coordinates(raw_node, attrs)
        if coords is None:
            continue

        node_id = f"{floor.id}:n:{node_index}"
        node_map[raw_node] = node_id
        nodes.append(
            {
                "id": node_id,
                "floor_id": str(floor.id),
                "floor_level": floor.level_number,
                "lng": coords[0],
                "lat": coords[1],
                "node_type": attrs.get("type") or "corridor",
                "name": attrs.get("name"),
                "space_type": attrs.get("space_type"),
            }
        )
        node_index += 1

    edge_index = 1
    for u, v, attrs in floor_graph.edges(data=True):
        if u not in node_map or v not in node_map:
            continue
        edges.append(
            {
                "id": f"{floor.id}:e:{edge_index}",
                "from": node_map[u],
                "to": node_map[v],
                "distance": float(attrs.get("weight") or 0.0),
                "edge_type": attrs.get("edge_type") or "corridor",
                "from_floor_id": str(floor.id),
                "to_floor_id": str(floor.id),
                "is_stitched": False,
            }
        )
        edge_index += 1

    return nodes, edges


def _stitch_adjacent_floors(floors: list[Floor], floor_nodes: dict[str, list[dict]]) -> list[dict]:
    stitched: list[dict] = []
    ordered = sorted(floors, key=lambda f: f.level_number)

    for idx in range(len(ordered) - 1):
        lower = ordered[idx]
        upper = ordered[idx + 1]
        
        # Only stitch adjacent levels (difference of 1)
        if upper.level_number - lower.level_number != 1:
            continue
        
        lower_nodes = floor_nodes.get(str(lower.id), [])
        upper_nodes = floor_nodes.get(str(upper.id), [])

        if not lower_nodes or not upper_nodes:
            continue

        lower_named = defaultdict(list)
        upper_named = defaultdict(list)
        for n in lower_nodes:
            name = _safe_name(n.get("name"))
            if name and _is_vertical_candidate(n):
                lower_named[name].append(n)
        for n in upper_nodes:
            name = _safe_name(n.get("name"))
            if name and _is_vertical_candidate(n):
                upper_named[name].append(n)

        stitched_this_pair = 0
        for name, source_candidates in lower_named.items():
            targets = upper_named.get(name)
            if not targets:
                continue
            source = source_candidates[0]
            target = targets[0]
            distance = max(
                abs(upper.level_number - lower.level_number) * DEFAULT_VERTICAL_TRAVEL_METERS,
                DEFAULT_VERTICAL_TRAVEL_METERS,
            )
            stitched.append(
                {
                    "id": f"stitch:{source['id']}:{target['id']}",
                    "from": source["id"],
                    "to": target["id"],
                    "distance": float(distance),
                    "edge_type": "vertical_connector",
                    "from_floor_id": str(lower.id),
                    "to_floor_id": str(upper.id),
                    "is_stitched": True,
                }
            )
            stitched_this_pair += 1

        if stitched_this_pair > 0:
            continue

        # Fallback: always stitch adjacent floors by nearest pair.
        best_pair = None
        best_distance = float("inf")
        for ln in lower_nodes:
            for un in upper_nodes:
                d = _distance_meters(ln["lng"], ln["lat"], un["lng"], un["lat"])
                if d < best_distance:
                    best_distance = d
                    best_pair = (ln, un)

        if best_pair:
            source, target = best_pair
            distance = max(
                abs(upper.level_number - lower.level_number) * DEFAULT_VERTICAL_TRAVEL_METERS,
                DEFAULT_VERTICAL_TRAVEL_METERS,
            )
            stitched.append(
                {
                    "id": f"stitch:{source['id']}:{target['id']}",
                    "from": source["id"],
                    "to": target["id"],
                    "distance": float(distance),
                    "edge_type": "vertical_connector",
                    "from_floor_id": str(lower.id),
                    "to_floor_id": str(upper.id),
                    "is_stitched": True,
                }
            )

    return stitched


async def _get_or_create_node_type(db: AsyncSession, code: str) -> NodeType:
    stmt: Select = select(NodeType).where(NodeType.code == code)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing
    created = NodeType(code=code, description=f"Auto-created node type: {code}")
    db.add(created)
    await db.flush()
    return created


async def _get_or_create_edge_type(db: AsyncSession, code: str, is_accessible: bool = True) -> EdgeType:
    stmt: Select = select(EdgeType).where(EdgeType.code == code)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing
    created = EdgeType(
        code=code,
        is_accessible=is_accessible,
        description=f"Auto-created edge type: {code}",
    )
    db.add(created)
    await db.flush()
    return created


async def get_active_graph_version(
    db: AsyncSession,
    building_id: uuid.UUID,
) -> NavigationGraphVersion | None:
    stmt = (
        select(NavigationGraphVersion)
        .where(
            NavigationGraphVersion.building_id == building_id,
            NavigationGraphVersion.is_active.is_(True),
        )
        .order_by(NavigationGraphVersion.version_number.desc())
    )
    return (await db.execute(stmt)).scalars().first()


async def build_graph_preview_for_building(db: AsyncSession, building_id: uuid.UUID) -> dict:
    building = await db.get(Building, building_id)
    if not building:
        raise ValueError("Building not found")

    floors_stmt = (
        select(Floor)
        .where(Floor.building_id == building_id)
        .order_by(Floor.level_number.asc())
    )
    floors = (await db.execute(floors_stmt)).scalars().all()
    if not floors:
        raise ValueError("No floors found for this building")

    all_nodes: list[dict] = []
    all_edges: list[dict] = []
    floor_nodes: dict[str, list[dict]] = {}

    for floor in floors:
        geojson = floor.floor_geojson or {"type": "FeatureCollection", "features": []}
        floor_graph = build_navigation_graph(geojson)
        nodes, edges = _preview_nodes_edges_for_floor(floor, floor_graph)
        floor_nodes[str(floor.id)] = nodes
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    stitched_edges = _stitch_adjacent_floors(floors, floor_nodes)
    all_edges.extend(stitched_edges)

    return {
        "building_id": str(building_id),
        "nodes": all_nodes,
        "edges": all_edges,
        "summary": {
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "stitched_edges": len(stitched_edges),
            "floors_processed": len(floors),
        },
    }


async def confirm_graph_preview(
    db: AsyncSession,
    building_id: uuid.UUID,
    preview: dict,
) -> dict:
    active_version = await get_active_graph_version(db, building_id)

    max_version_stmt = select(func.max(NavigationGraphVersion.version_number)).where(
        NavigationGraphVersion.building_id == building_id
    )
    max_version = (await db.execute(max_version_stmt)).scalar() or 0

    if active_version:
        # Instance-level toggle is resilient in unit tests that patch model classes.
        active_version.is_active = False

    new_version = NavigationGraphVersion(
        building_id=building_id,
        version_number=int(max_version) + 1,
        is_active=True,
    )
    db.add(new_version)
    await db.flush()

    node_id_to_db_uuid: dict[str, uuid.UUID] = {}
    created_nodes = 0
    created_edges = 0

    for node in preview.get("nodes", []):
        node_type_code = (node.get("node_type") or "corridor").lower()
        node_type = await _get_or_create_node_type(db, node_type_code)

        db_node_id = uuid.uuid4()
        node_id_to_db_uuid[node["id"]] = db_node_id

        db.add(
            RoutingNode(
                id=db_node_id,
                floor_id=uuid.UUID(node["floor_id"]),
                node_type_id=node_type.id,
                graph_version_id=new_version.id,
                geometry=WKTElement(f"POINT({node['lng']} {node['lat']})", srid=4326),
            )
        )
        created_nodes += 1

    await db.flush()

    for edge in preview.get("edges", []):
        from_id = node_id_to_db_uuid.get(edge.get("from"))
        to_id = node_id_to_db_uuid.get(edge.get("to"))
        if not from_id or not to_id:
            continue

        edge_type_code = (edge.get("edge_type") or "corridor").lower()
        edge_type = await _get_or_create_edge_type(db, edge_type_code, is_accessible=True)

        db.add(
            RoutingEdge(
                id=uuid.uuid4(),
                from_node_id=from_id,
                to_node_id=to_id,
                edge_type_id=edge_type.id,
                graph_version_id=new_version.id,
                distance=max(float(edge.get("distance") or 0.0), 0.01),
            )
        )
        created_edges += 1

    await db.commit()

    return {
        "graph_version_id": str(new_version.id),
        "version_number": new_version.version_number,
        "previous_active_version_id": str(active_version.id) if active_version else None,
        "persisted": {
            "nodes": created_nodes,
            "edges": created_edges,
            "floors": preview.get("summary", {}).get("floors_processed", 0),
        },
    }


async def rollback_to_previous_graph_version(db: AsyncSession, building_id: uuid.UUID) -> dict:
    versions_stmt = (
        select(NavigationGraphVersion)
        .where(NavigationGraphVersion.building_id == building_id)
        .order_by(NavigationGraphVersion.version_number.desc())
    )
    versions = (await db.execute(versions_stmt)).scalars().all()

    active = next((v for v in versions if v.is_active), None)
    if not active:
        raise ValueError("No active graph version found")

    if len(versions) < 2:
        raise ValueError("No previous graph version available for rollback")

    previous_candidates = [v for v in versions if v.version_number < active.version_number]
    if not previous_candidates:
        raise ValueError("No previous graph version available for rollback")

    previous = previous_candidates[0]

    await db.execute(
        update(NavigationGraphVersion)
        .where(NavigationGraphVersion.building_id == building_id)
        .values(is_active=False)
    )
    await db.execute(
        update(NavigationGraphVersion)
        .where(NavigationGraphVersion.id == previous.id)
        .values(is_active=True)
    )
    await db.commit()

    return {
        "rolled_back_to_version_id": str(previous.id),
        "rolled_back_to_version_number": previous.version_number,
        "previous_active_version_id": str(active.id),
        "previous_active_version_number": active.version_number,
    }
