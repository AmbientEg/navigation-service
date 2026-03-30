import networkx as nx
import inspect
import math
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsText, ST_Distance, ST_X, ST_Y
from models.routing_nodes import RoutingNode
from models.routing_edges import RoutingEdge
from models.edge_types import EdgeType
from models.floors import Floor
from models.navigation_graph_versions import NavigationGraphVersion
from models.poi import POI
import uuid
from typing import List, Tuple, Optional


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _parse_wkt_point(point_wkt: str) -> Optional[Tuple[float, float]]:
    if not point_wkt or not isinstance(point_wkt, str):
        return None
    text = point_wkt.strip()
    if not text.startswith("POINT(") or not text.endswith(")"):
        return None
    try:
        coords = text.replace("POINT(", "").replace(")", "").split()
        return float(coords[0]), float(coords[1])
    except (ValueError, IndexError):
        return None


def _extract_node_lng_lat(node) -> Tuple[float, float]:
    lng = getattr(node, "lng", None)
    lat = getattr(node, "lat", None)
    if lng is not None and lat is not None:
        return float(lng), float(lat)

    x = getattr(node, "x", None)
    y = getattr(node, "y", None)
    if x is not None and y is not None:
        return float(x), float(y)

    point = _parse_wkt_point(getattr(node, "geometry_wkt", None))
    if point:
        return point

    # Safe fallback for mocked nodes that do not expose coordinate fields.
    return 0.0, 0.0


def _distance_meters(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Fast local approximation suitable for indoor-scale paths."""
    avg_lat_rad = math.radians((lat1 + lat2) / 2.0)
    meters_per_deg_lat = 111_132.0
    meters_per_deg_lng = 111_320.0 * math.cos(avg_lat_rad)
    dx = (lng2 - lng1) * meters_per_deg_lng
    dy = (lat2 - lat1) * meters_per_deg_lat
    return (dx * dx + dy * dy) ** 0.5


def _path_distance_meters_from_nodes(G: nx.Graph, path: List[str]) -> float:
    total = 0.0
    for i in range(1, len(path)):
        prev_node = G.nodes[path[i - 1]]
        curr_node = G.nodes[path[i]]
        segment = _distance_meters(
            float(prev_node["lng"]),
            float(prev_node["lat"]),
            float(curr_node["lng"]),
            float(curr_node["lat"]),
        )
        total += max(segment, 0.01)
    return total


def _bearing_degrees(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Initial bearing from point A to B in degrees [0, 360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    lam1 = math.radians(lng1)
    lam2 = math.radians(lng2)
    d_lam = lam2 - lam1

    y = math.sin(d_lam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lam)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _compass_direction(bearing_deg: float) -> str:
    directions = [
        "north",
        "north-east",
        "east",
        "south-east",
        "south",
        "south-west",
        "west",
        "north-west",
    ]
    idx = int((bearing_deg + 22.5) // 45) % 8
    return directions[idx]


def _turn_phrase(prev_bearing: float, next_bearing: float) -> str:
    """Map bearing delta to a user-friendly turn instruction."""
    delta = (next_bearing - prev_bearing + 540.0) % 360.0 - 180.0
    abs_delta = abs(delta)
    if abs_delta < 25.0:
        return "Continue straight"
    if delta > 0:
        if abs_delta < 60.0:
            return "Slight right"
        if abs_delta < 120.0:
            return "Turn right"
        return "Make a sharp right"
    if abs_delta < 60.0:
        return "Slight left"
    if abs_delta < 120.0:
        return "Turn left"
    return "Make a sharp left"


async def find_nearest_node(
    db: AsyncSession,
    floor_id: uuid.UUID,
    lat: float,
    lng: float,
    graph_version_id: uuid.UUID,
) -> Optional[RoutingNode]:
    """Find the nearest routing node to a given coordinate on a floor."""
    # Build a typed geometry point to avoid SRID=0 literals in PostGIS.
    query_point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)

    # Using ST_Distance to find the closest node
    result = await db.execute(
        select(RoutingNode)
        .where(
            RoutingNode.floor_id == floor_id,
            RoutingNode.graph_version_id == graph_version_id,
        )
        .order_by(
            ST_Distance(
                RoutingNode.geometry,
                query_point,
            )
        )
        .limit(1)
    )
    return await _await_if_needed(result.scalar_one_or_none())


async def build_graph_for_floors(
    db: AsyncSession,
    floor_ids: List[uuid.UUID],
    graph_version_id: uuid.UUID,
    accessible_only: bool = False
) -> nx.Graph:
    """Build a NetworkX graph from routing nodes and edges for given floors."""
    G = nx.Graph()

    if not floor_ids:
        return G
    
    # Get all nodes for the floors
    nodes_result = await db.execute(
        select(
            RoutingNode,
            ST_X(RoutingNode.geometry).label("lng"),
            ST_Y(RoutingNode.geometry).label("lat"),
        )
        .where(
            RoutingNode.floor_id.in_(floor_ids),
            RoutingNode.graph_version_id == graph_version_id,
        )
    )
    node_rows = await _await_if_needed(nodes_result.all())
    nodes = [row[0] for row in node_rows]
    
    # Add nodes to graph with their coordinates
    for row in node_rows:
        node = row[0]
        lng = row[1]
        lat = row[2]
        if lng is None or lat is None:
            lng, lat = _extract_node_lng_lat(node)
        
        G.add_node(
            str(node.id),
            floor_id=str(node.floor_id),
            lat=float(lat),
            lng=float(lng),
            node_type_id=str(node.node_type_id)
        )
    
    # Get all edges for these nodes
    node_ids = [node.id for node in nodes]
    edges_query = select(RoutingEdge).where(
        RoutingEdge.from_node_id.in_(node_ids),
        RoutingEdge.to_node_id.in_(node_ids),
        RoutingEdge.graph_version_id == graph_version_id,
    )
    
    if accessible_only:
        edges_query = edges_query.join(EdgeType).where(EdgeType.is_accessible == True)
    
    edges_result = await db.execute(edges_query)
    edge_scalars = await _await_if_needed(edges_result.scalars())
    edges = await _await_if_needed(edge_scalars.all())
    
    # Add edges to graph
    for edge in edges:
        G.add_edge(
            str(edge.from_node_id),
            str(edge.to_node_id),
            weight=edge.distance,
            edge_type_id=str(edge.edge_type_id)
        )
    
    return G


async def calculate_route(
    db: AsyncSession,
    from_floor_id: uuid.UUID,
    from_lat: float,
    from_lng: float,
    to_poi_id: uuid.UUID,
    accessible: bool = True
) -> dict:
    """
    Calculate the route from a point to a POI.
    
    Returns a dict with:
    - floors: list of floor paths with coordinates
    - distance: total distance in meters
    - steps: list of navigation instructions
    """
    # Get destination POI
    poi = await db.get(POI, to_poi_id)
    if not poi:
        raise ValueError("POI not found")

    from_floor = await db.get(Floor, from_floor_id)
    to_floor = await db.get(Floor, poi.floor_id)
    if not from_floor or not to_floor:
        raise ValueError("Source or destination floor not found")
    if from_floor.building_id != to_floor.building_id:
        raise ValueError("Cross-building routing is not supported")

    active_version_stmt = (
        select(NavigationGraphVersion)
        .where(
            NavigationGraphVersion.building_id == from_floor.building_id,
            NavigationGraphVersion.is_active.is_(True),
        )
        .order_by(NavigationGraphVersion.version_number.desc())
    )
    active_graph_version = (await db.execute(active_version_stmt)).scalars().first()
    if not active_graph_version:
        raise ValueError("No active navigation graph version found for this building")
    
    # Get POI coordinates
    poi_coords_result = await db.execute(select(ST_AsText(poi.geometry)))
    poi_coords_text = await _await_if_needed(poi_coords_result.scalar())
    poi_point = _parse_wkt_point(poi_coords_text)
    if not poi_point:
        raise ValueError("Invalid POI geometry")
    poi_lng, poi_lat = poi_point
    
    # Find nearest nodes to start and end points
    start_node = await find_nearest_node(
        db,
        from_floor_id,
        from_lat,
        from_lng,
        active_graph_version.id,
    )
    end_node = await find_nearest_node(
        db,
        poi.floor_id,
        poi_lat,
        poi_lng,
        active_graph_version.id,
    )
    
    if not start_node or not end_node:
        raise ValueError("Could not find routing nodes near start or destination")
    
    # Collect all relevant floors
    floor_ids = list({from_floor_id, poi.floor_id})
    
    # Build graph
    G = await build_graph_for_floors(db, floor_ids, active_graph_version.id, accessible)
    
    if not nx.has_path(G, str(start_node.id), str(end_node.id)):
        raise ValueError("No route found between start and destination")
    
    # Calculate shortest path
    path = nx.shortest_path(
        G,
        source=str(start_node.id),
        target=str(end_node.id),
        weight="weight"
    )
    
    # Calculate total distance from graph weights first.
    total_distance = nx.shortest_path_length(
        G,
        source=str(start_node.id),
        target=str(end_node.id),
        weight="weight"
    )

    # Legacy graph versions may store tiny degree-based edge weights.
    # If path length is suspiciously small, derive meters from node coordinates.
    if total_distance < 1.0:
        geometric_distance = _path_distance_meters_from_nodes(G, path)
        if geometric_distance > 0:
            total_distance = geometric_distance
    
    # Group path by floors
    floors_data = {}
    for node_id in path:
        node_data = G.nodes[node_id]
        floor_id = node_data["floor_id"]
        if floor_id not in floors_data:
            floors_data[floor_id] = []
        floors_data[floor_id].append([node_data["lng"], node_data["lat"]])
    
    # Build response
    floors = [
        {
            "floorId": floor_id,
            "path": coords
        }
        for floor_id, coords in floors_data.items()
    ]
    
    # Generate simple navigation steps
    steps = generate_steps(G, path, from_lng, from_lat, poi_lng, poi_lat)
    
    return {
        "floors": floors,
        "distance": round(total_distance, 2),
        "steps": steps
    }


def generate_steps(
    G: nx.Graph,
    path: List[str],
    start_lng: float,
    start_lat: float,
    end_lng: float,
    end_lat: float
) -> List[str]:
    """Generate human-readable navigation steps."""
    steps = []
    
    if len(path) == 0:
        return ["You have arrived"]
    if len(path) == 1:
        return ["You have arrived at your destination"]
    
    node_data = [G.nodes[node_id] for node_id in path]
    segment_distances: List[float] = []
    segment_bearings: List[float] = []
    for i in range(1, len(node_data)):
        prev_node = node_data[i - 1]
        curr_node = node_data[i]
        seg_m = _distance_meters(
            float(prev_node["lng"]),
            float(prev_node["lat"]),
            float(curr_node["lng"]),
            float(curr_node["lat"]),
        )
        segment_distances.append(max(seg_m, 0.01))
        segment_bearings.append(
            _bearing_degrees(
                float(prev_node["lng"]),
                float(prev_node["lat"]),
                float(curr_node["lng"]),
                float(curr_node["lat"]),
            )
        )

    start_floor = node_data[0]["floor_id"]
    end_floor = node_data[-1]["floor_id"]
    heading = _compass_direction(segment_bearings[0])
    if start_floor != end_floor:
        steps.append(f"Start on floor {start_floor} and head {heading}")
    else:
        steps.append(f"Head {heading} towards destination")

    current_phrase = "Continue straight"
    current_distance = segment_distances[0]
    for seg_idx in range(1, len(segment_distances)):
        next_floor = node_data[seg_idx + 1]["floor_id"]

        if node_data[seg_idx]["floor_id"] != next_floor:
            steps.append(f"{current_phrase} for {round(current_distance, 1)}m")
            steps.append(f"Change to floor {next_floor}")
            current_phrase = "Continue straight"
            current_distance = segment_distances[seg_idx]
            continue

        turn = _turn_phrase(segment_bearings[seg_idx - 1], segment_bearings[seg_idx])
        if turn == "Continue straight":
            current_distance += segment_distances[seg_idx]
        else:
            steps.append(f"{current_phrase} for {round(current_distance, 1)}m")
            current_phrase = turn
            current_distance = segment_distances[seg_idx]

    steps.append(f"{current_phrase} for {round(current_distance, 1)}m")
    
    steps.append("You have arrived at your destination")
    
    return steps


def build_graph(nodes, edges):
    """Legacy function for backward compatibility."""
    G = nx.Graph()
    for node in nodes:
        G.add_node(str(node.id), data=node)
    for edge in edges:
        G.add_edge(str(edge.from_node_id), str(edge.to_node_id), weight=edge.distance)
    return G


def shortest_path(G, start_node, end_node):
    """Legacy function for backward compatibility."""
    path = nx.shortest_path(G, source=str(start_node), target=str(end_node), weight="weight")
    return path
