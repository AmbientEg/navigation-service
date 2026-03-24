"""
Runtime navigation service for calculating routes and nearest-node searches.

CRS Policy:
- All inputs and outputs use WGS84 (lat/lng).
- All database geometries are stored in SRID=4326 (WGS84).
- PostGIS distance calculations use geography type for meter-accurate distances.
- Points created in queries must explicitly set SRID=4326.

Key Design Decisions:
1. find_nearest_node() uses ST_SetSRID + ST_Distance with geography casting.
2. build_graph_for_floors() batch-loads coordinates efficiently and validates CRS.
3. All input coordinates (lat, lng) are validated against WGS84 ranges.
"""

import logging
import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsText, ST_SetSRID, ST_DistanceSphere
from geoalchemy2 import WKTElement
from models.routing_nodes import RoutingNode
from models.routing_edges import RoutingEdge
from models.edge_types import EdgeType
from models.poi import POI
from services.crs_service import validate_wgs84_coordinates
import uuid
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Constants
WGS84_SRID = 4326


async def find_nearest_node(
    db: AsyncSession,
    floor_id: uuid.UUID,
    lat: float,
    lng: float
) -> Optional[RoutingNode]:
    """
    Find the nearest routing node to a given WGS84 coordinate on a floor.
    
    This function uses PostGIS geography functions for accurate meter-based distance
    calculations. All coordinates are in WGS84 (EPSG:4326).
    
    Args:
        db: Async database session
        floor_id: Target floor UUID
        lat: Latitude in WGS84 (-90 to 90)
        lng: Longitude in WGS84 (-180 to 180)
    
    Returns:
        RoutingNode: Nearest node or None if no nodes found on floor
    
    Raises:
        ValueError: If input coordinates are invalid WGS84
    """
    # Validate input coordinates are within WGS84 range
    if not validate_wgs84_coordinates(lng, lat):
        raise ValueError(f"Invalid WGS84 coordinates: lng={lng}, lat={lat}")
    
    logger.debug(f"Finding nearest node on floor {floor_id} for ({lat}, {lng})")
    
    # Create query point in WGS84.
    # ST_SetSRID() ensures the point has SRID=4326.
    # Use ST_DistanceSphere for meter-based distance in WGS84.
    query_point_wkt = f"POINT({lng} {lat})"
    
    result = await db.execute(
        select(RoutingNode)
        .where(RoutingNode.floor_id == floor_id)
        .order_by(
            # ST_DistanceSphere gives meter distance for lon/lat points.
            ST_DistanceSphere(
                RoutingNode.geometry,
                ST_SetSRID(WKTElement(query_point_wkt, srid=WGS84_SRID), WGS84_SRID)
            )
        )
        .limit(1)
    )
    
    node = result.scalar_one_or_none()
    if node:
        logger.debug(f"Found nearest node {node.id} at {node.name or 'unknown'}")
    else:
        logger.warning(f"No nodes found on floor {floor_id}")
    
    return node


async def build_graph_for_floors(
    db: AsyncSession,
    floor_ids: List[uuid.UUID],
    accessible_only: bool = False
) -> nx.Graph:
    """
    Build a NetworkX graph from routing nodes and edges for given floors.
    
    This function efficiently loads all nodes and edges with explicit CRS handling:
    - All coordinates are in WGS84 from the database.
    - Batch-loads coordinates to avoid N+1 query problem.
    - Validates that all node coordinates are within valid WGS84 ranges.
    
    Args:
        db: Async database session
        floor_ids: List of floor UUIDs to include
        accessible_only: If True, only include edges marked as accessible
    
    Returns:
        nx.Graph: NetworkX graph with nodes and edges
    
    Raises:
        ValueError: If any node has invalid coordinates
    """
    G = nx.Graph()
    
    logger.info(f"Building graph for {len(floor_ids)} floor(s)")
    
    # ===== BATCH LOAD NODES =====
    # Avoid N+1 problem by fetching all node coordinates in one query.
    # Cast geometry to text representation for parsing.
    nodes_query = (
        select(
            RoutingNode.id,
            RoutingNode.floor_id,
            RoutingNode.node_type_id,
            RoutingNode.name,
            ST_AsText(RoutingNode.geometry).label("geom_text")
        )
        .where(RoutingNode.floor_id.in_(floor_ids))
    )
    
    nodes_result = await db.execute(nodes_query)
    nodes_data = nodes_result.all()
    
    logger.debug(f"Loaded {len(nodes_data)} nodes for graph building")
    
    # Track node IDs for edge lookup
    node_ids_to_db_ids = {}
    
    # Add nodes to graph, validating CRS along the way
    for node_id, floor_id, node_type_id, name, geom_text in nodes_data:
        try:
            # Parse WKT: "POINT(lng lat)"
            geom_text_clean = geom_text.replace("POINT(", "").replace(")", "").strip()
            coords = geom_text_clean.split()
            
            if len(coords) < 2:
                logger.error(f"Invalid geometry text for node {node_id}: {geom_text}")
                continue
            
            lng, lat = float(coords[0]), float(coords[1])
            
            # ===== CRS VALIDATION: Ensure coordinates are in WGS84 =====
            if not validate_wgs84_coordinates(lng, lat):
                logger.error(
                    f"Node {node_id} has out-of-range WGS84 coordinates: lng={lng}, lat={lat}. "
                    f"Possible CRS mismatch. Skipping node."
                )
                continue
            
            # Add to graph with WGS84 coordinates
            G.add_node(
                str(node_id),
                floor_id=str(floor_id),
                lat=lat,
                lng=lng,
                node_type_id=str(node_type_id),
                name=name
            )
            node_ids_to_db_ids[node_id] = node_id
            
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse node geometry: {e}")
            continue
    
    # ===== BATCH LOAD EDGES =====
    # Fetch all edges for the nodes we successfully loaded
    node_ids = list(node_ids_to_db_ids.keys())
    
    edges_query = select(RoutingEdge).where(
        RoutingEdge.from_node_id.in_(node_ids),
        RoutingEdge.to_node_id.in_(node_ids)
    )
    
    if accessible_only:
        edges_query = edges_query.join(EdgeType).where(EdgeType.is_accessible == True)
    
    edges_result = await db.execute(edges_query)
    edges = edges_result.scalars().all()
    
    logger.debug(f"Loaded {len(edges)} edges for graph")
    
    # Add edges to graph with distance (in meters)
    edges_added = 0
    for edge in edges:
        from_node_str = str(edge.from_node_id)
        to_node_str = str(edge.to_node_id)
        
        # Only add edge if both nodes are in the graph
        if from_node_str in G.nodes and to_node_str in G.nodes:
            G.add_edge(
                from_node_str,
                to_node_str,
                weight=edge.distance,  # Distance in meters (from pipeline)
                edge_type_id=str(edge.edge_type_id)
            )
            edges_added += 1
        else:
            logger.warning(
                f"Edge from {edge.from_node_id} to {edge.to_node_id} has missing node(s). Skipping."
            )
    
    logger.info(f"Graph built: {G.number_of_nodes()} nodes, {edges_added} edges")
    
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
    Calculate the route from a WGS84 point to a POI.
    
    All input coordinates must be in WGS84 (lat/lng). The function:
    1. Validates input coordinates are within WGS84 ranges.
    2. Finds nearest nodes using CRS-safe geography-based distance.
    3. Builds graph with coordinate validation.
    4. Calculates shortest path using NetworkX.
    5. Returns organized route with distance and steps.
    
    Args:
        db: Async database session
        from_floor_id: Starting floor UUID
        from_lat: Starting latitude in WGS84
        from_lng: Starting longitude in WGS84
        to_poi_id: Destination POI UUID
        accessible: If True, only use accessible edges
    
    Returns:
        dict: Route with keys:
            - floors: List of floor paths with [lng, lat] coordinates
            - distance: Total distance in meters
            - steps: List of navigation instructions
    
    Raises:
        ValueError: If coordinates invalid or route not found
    """
    # ===== VALIDATE INPUT COORDINATES =====
    if not validate_wgs84_coordinates(from_lng, from_lat):
        raise ValueError(f"Invalid starting WGS84 coordinates: lng={from_lng}, lat={from_lat}")
    
    logger.info(f"Calculating route from ({from_lat}, {from_lng}) to POI {to_poi_id}")
    
    # ===== GET DESTINATION POI =====
    poi = await db.get(POI, to_poi_id)
    if not poi:
        raise ValueError(f"POI {to_poi_id} not found")
    
    logger.debug(f"Destination POI: {poi.name} on floor {poi.floor_id}")
    
    # ===== EXTRACT POI COORDINATES =====
    # POI geometry is stored in WGS84 in the database.
    poi_coords_result = await db.execute(select(ST_AsText(poi.geometry)))
    poi_coords_text = poi_coords_result.scalar()
    
    if not poi_coords_text:
        raise ValueError(f"POI {to_poi_id} has no geometry")
    
    # Parse WKT: "POINT(lng lat)"
    poi_coords = poi_coords_text.replace("POINT(", "").replace(")", "").split()
    poi_lng, poi_lat = float(poi_coords[0]), float(poi_coords[1])
    
    # Validate POI coordinates
    if not validate_wgs84_coordinates(poi_lng, poi_lat):
        raise ValueError(f"POI has invalid WGS84 coordinates: lng={poi_lng}, lat={poi_lat}")
    
    # ===== FIND NEAREST NODES =====
    start_node = await find_nearest_node(db, from_floor_id, from_lat, from_lng)
    end_node = await find_nearest_node(db, poi.floor_id, poi_lat, poi_lng)
    
    if not start_node:
        raise ValueError(f"Could not find routing node near start ({from_lat}, {from_lng}) on floor {from_floor_id}")
    if not end_node:
        raise ValueError(f"Could not find routing node near destination ({poi_lat}, {poi_lng}) on floor {poi.floor_id}")
    
    logger.debug(f"Start node: {start_node.id}, End node: {end_node.id}")
    
    # ===== BUILD GRAPH =====
    floor_ids = list({from_floor_id, poi.floor_id})
    G = await build_graph_for_floors(db, floor_ids, accessible_only=accessible)
    
    if G.number_of_nodes() == 0:
        raise ValueError("No routing nodes found for requested floors")
    
    # Check if path exists
    if not nx.has_path(G, str(start_node.id), str(end_node.id)):
        raise ValueError(f"No route found between start node {start_node.id} and destination {end_node.id}")
    
    # ===== CALCULATE SHORTEST PATH =====
    path = nx.shortest_path(
        G,
        source=str(start_node.id),
        target=str(end_node.id),
        weight="weight"
    )
    
    # Calculate total distance
    total_distance = nx.shortest_path_length(
        G,
        source=str(start_node.id),
        target=str(end_node.id),
        weight="weight"
    )
    
    logger.info(f"Route found: {len(path)} nodes, {round(total_distance, 2)}m total distance")
    
    # ===== GROUP PATH BY FLOORS =====
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
    
    # Generate navigation steps
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
    """
    Generate human-readable navigation steps from a path.
    
    Current implementation uses simple heuristics:
    - Detects floor transitions
    - Adds distance markers every 5 nodes
    
    Future enhancement: Calculate turn angles between consecutive node triples
    to generate turn-specific instructions (left, right, straight, u-turn).
    
    Args:
        G: NetworkX graph with path nodes and edges
        path: List of node IDs representing the route
        start_lng: Starting longitude
        start_lat: Starting latitude
        end_lng: Destination longitude
        end_lat: Destination latitude
    
    Returns:
        List[str]: Human-readable navigation instructions
    """
    steps = []
    
    if len(path) == 0:
        return ["You have arrived"]
    
    # Add start instruction
    first_node = G.nodes[path[0]]
    if first_node["floor_id"] != G.nodes[path[-1]]["floor_id"]:
        steps.append(f"Start on floor {first_node['floor_id']}")
    else:
        steps.append("Head towards destination")
    
    # Detect floor changes and add distance markers
    current_floor = None
    for i, node_id in enumerate(path):
        node = G.nodes[node_id]
        if current_floor is None:
            current_floor = node["floor_id"]
        elif current_floor != node["floor_id"]:
            steps.append(f"Change to floor {node['floor_id']}")
            current_floor = node["floor_id"]
        
        # Add distance markers every few nodes
        if i > 0 and i % 5 == 0 and i < len(path) - 1:
            edge_data = G.get_edge_data(path[i-1], node_id)
            if edge_data:
                steps.append(f"Continue straight for {round(edge_data['weight'], 1)}m")
    
    steps.append("You have arrived at your destination")
    
    return steps


def build_graph(nodes, edges):
    """
    Legacy function for backward compatibility.
    
    Creates a simple NetworkX graph from node and edge lists.
    Does not include CRS validation; use build_graph_for_floors() instead
    for production code that requires CRS safety.
    """
    G = nx.Graph()
    for node in nodes:
        G.add_node(str(node.id), data=node)
    for edge in edges:
        G.add_edge(str(edge.from_node_id), str(edge.to_node_id), weight=edge.distance)
    return G


def shortest_path(G, start_node, end_node):
    """
    Legacy function for backward compatibility.
    
    Calculates shortest path using NetworkX.
    """
    path = nx.shortest_path(G, source=str(start_node), target=str(end_node), weight="weight")
    return path
