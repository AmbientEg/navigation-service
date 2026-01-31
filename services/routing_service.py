import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_Distance, ST_AsText
from models.routing_nodes import RoutingNode
from models.routing_edges import RoutingEdge
from models.edge_types import EdgeType
from models.poi import POI
import uuid
from typing import List, Tuple, Optional


async def find_nearest_node(
    db: AsyncSession,
    floor_id: uuid.UUID,
    lat: float,
    lng: float
) -> Optional[RoutingNode]:
    """Find the nearest routing node to a given coordinate on a floor."""
    # Using ST_Distance to find the closest node
    result = await db.execute(
        select(RoutingNode)
        .where(RoutingNode.floor_id == floor_id)
        .order_by(
            ST_Distance(
                RoutingNode.geometry,
                f"POINT({lng} {lat})"
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_graph_for_floors(
    db: AsyncSession,
    floor_ids: List[uuid.UUID],
    accessible_only: bool = False
) -> nx.Graph:
    """Build a NetworkX graph from routing nodes and edges for given floors."""
    G = nx.Graph()
    
    # Get all nodes for the floors
    nodes_result = await db.execute(
        select(RoutingNode)
        .where(RoutingNode.floor_id.in_(floor_ids))
    )
    nodes = nodes_result.scalars().all()
    
    # Add nodes to graph with their coordinates
    for node in nodes:
        coords_result = await db.execute(
            select(ST_AsText(node.geometry))
        )
        coords_text = coords_result.scalar()
        # Parse POINT(lng lat) format
        coords = coords_text.replace("POINT(", "").replace(")", "").split()
        lng, lat = float(coords[0]), float(coords[1])
        
        G.add_node(
            str(node.id),
            floor_id=str(node.floor_id),
            lat=lat,
            lng=lng,
            node_type_id=str(node.node_type_id)
        )
    
    # Get all edges for these nodes
    node_ids = [node.id for node in nodes]
    edges_query = select(RoutingEdge).where(
        RoutingEdge.from_node_id.in_(node_ids),
        RoutingEdge.to_node_id.in_(node_ids)
    )
    
    if accessible_only:
        edges_query = edges_query.join(EdgeType).where(EdgeType.is_accessible == True)
    
    edges_result = await db.execute(edges_query)
    edges = edges_result.scalars().all()
    
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
    
    # Get POI coordinates
    poi_coords_result = await db.execute(select(ST_AsText(poi.geometry)))
    poi_coords_text = poi_coords_result.scalar()
    poi_coords = poi_coords_text.replace("POINT(", "").replace(")", "").split()
    poi_lng, poi_lat = float(poi_coords[0]), float(poi_coords[1])
    
    # Find nearest nodes to start and end points
    start_node = await find_nearest_node(db, from_floor_id, from_lat, from_lng)
    end_node = await find_nearest_node(db, poi.floor_id, poi_lat, poi_lng)
    
    if not start_node or not end_node:
        raise ValueError("Could not find routing nodes near start or destination")
    
    # Collect all relevant floors
    floor_ids = list({from_floor_id, poi.floor_id})
    
    # Build graph
    G = await build_graph_for_floors(db, floor_ids, accessible)
    
    if not nx.has_path(G, str(start_node.id), str(end_node.id)):
        raise ValueError("No route found between start and destination")
    
    # Calculate shortest path
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
    
    # Add start instruction
    first_node = G.nodes[path[0]]
    if first_node["floor_id"] != G.nodes[path[-1]]["floor_id"]:
        steps.append(f"Start on floor {first_node['floor_id']}")
    else:
        steps.append("Head towards destination")
    
    # Detect floor changes
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
