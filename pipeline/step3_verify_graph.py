import networkx as nx
from shapely.geometry import Point
from typing import Dict, List, Tuple, Optional
import statistics
import json

# =========================
# SETTINGS
# =========================
MIN_EDGE_WEIGHT = 1e-9  # Threshold for zero-length edges
VERTICAL_MOVEMENT_TYPES = {"stairs", "elevator", "entrance", "exit"}  # Types indicating vertical movement

# =========================
# VERIFY EDGE WEIGHTS
# =========================
def verify_edge_weights(G: nx.Graph) -> Tuple[List[Tuple], int]:
    """
    Check all edges have positive, non-zero weights.
    
    Returns:
        - List of problematic edges (u, v, weight)
        - Count of edges fixed
    """
    problematic_edges = []
    fixed_count = 0
    
    for u, v, data in G.edges(data=True):
        weight = data.get("weight")
        
        # Check if weight is missing
        if weight is None:
            # Calculate Euclidean distance from node coordinates
            coords_u = _extract_node_coordinates(u, G.nodes[u])
            coords_v = _extract_node_coordinates(v, G.nodes[v])
            
            if coords_u and coords_v:
                calculated_weight = Point(coords_u).distance(Point(coords_v))
                G[u][v]["weight"] = calculated_weight
                fixed_count += 1
            else:
                problematic_edges.append((u, v, weight))
        
        # Check if weight is zero or negative
        elif weight <= 0 or weight < MIN_EDGE_WEIGHT:
            problematic_edges.append((u, v, weight))
    
    return problematic_edges, fixed_count


# =========================
# VERIFY NODE COORDINATES
# =========================
def verify_node_coordinates(G: nx.Graph) -> Tuple[List, int]:
    """
    Ensure all nodes have valid coordinates.
    
    Nodes can have coordinates either as:
    - Tuple/list node key: (x, y)
    - Attributes: x, y or lat, lng
    
    Returns:
        - List of nodes with invalid coordinates
        - Count of nodes validated
    """
    invalid_nodes = []
    valid_count = 0
    
    for node, attrs in G.nodes(data=True):
        coords = _extract_node_coordinates(node, attrs)
        if coords is None:
            invalid_nodes.append(node)
        else:
            valid_count += 1
    
    return invalid_nodes, valid_count


# =========================
# FLAG VERTICAL MOVEMENT EDGES
# =========================
def flag_vertical_movement_edges(G: nx.Graph) -> int:
    """
    Flag edges representing vertical movement (stairs, elevators).
    Adds 'is_vertical' attribute to edges.
    
    Returns:
        Count of vertical movement edges flagged
    """
    vertical_count = 0
    
    for u, v, data in G.edges(data=True):
        edge_type = data.get("edge_type", "").lower()
        
        # Check if edge connects to vertical movement nodes
        u_type = G.nodes[u].get("type", "").lower()
        v_type = G.nodes[v].get("type", "").lower()
        
        is_vertical = (
            edge_type in VERTICAL_MOVEMENT_TYPES or
            u_type in VERTICAL_MOVEMENT_TYPES or
            v_type in VERTICAL_MOVEMENT_TYPES
        )
        
        if is_vertical:
            G[u][v]["is_vertical"] = True
            vertical_count += 1
        else:
            G[u][v]["is_vertical"] = False
    
    return vertical_count


# =========================
# CALCULATE STATISTICS
# =========================
def calculate_edge_statistics(G: nx.Graph) -> Dict:
    """
    Calculate summary statistics for edge weights.
    
    Returns:
        Dictionary with min, max, avg, and count of edge weights
    """
    weights = []
    
    for u, v, data in G.edges(data=True):
        weight = data.get("weight")
        if weight is not None and weight > 0:
            weights.append(weight)
    
    if not weights:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "avg": None,
            "median": None,
            "std_dev": None
        }
    
    return {
        "count": len(weights),
        "min": min(weights),
        "max": max(weights),
        "avg": statistics.mean(weights),
        "median": statistics.median(weights),
        "std_dev": statistics.stdev(weights) if len(weights) > 1 else 0
    }


# =========================
# NODE TYPE DISTRIBUTION
# =========================
def get_node_type_distribution(G: nx.Graph) -> Dict[str, int]:
    """
    Get distribution of node types in the graph.
    
    Returns:
        Dictionary mapping node types to counts
    """
    distribution = {}
    
    for node, attrs in G.nodes(data=True):
        node_type = attrs.get("type", "unknown")
        distribution[node_type] = distribution.get(node_type, 0) + 1
    
    return distribution


# =========================
# EDGE TYPE DISTRIBUTION
# =========================
def get_edge_type_distribution(G: nx.Graph) -> Dict[str, int]:
    """
    Get distribution of edge types in the graph.
    
    Returns:
        Dictionary mapping edge types to counts
    """
    distribution = {}
    
    for u, v, data in G.edges(data=True):
        edge_type = data.get("edge_type", "unknown")
        distribution[edge_type] = distribution.get(edge_type, 0) + 1
    
    return distribution


# =========================
# HELPER: Extract Coordinates
# =========================
def _extract_node_coordinates(node, attrs) -> Optional[Tuple[float, float]]:
    """
    Resolve node coordinates from tuple key or attributes.
    
    Supports:
      - Tuple/list node keys: (x, y)
      - Node attributes: x, y
      - Node attributes: lat, lng (alternative)
    
    Returns:
        (x, y) tuple or None if coordinates cannot be resolved
    """
    # Check if node key is a tuple/list coordinate
    if isinstance(node, (tuple, list)) and len(node) >= 2:
        try:
            return float(node[0]), float(node[1])
        except (ValueError, TypeError):
            pass
    
    # Check node attributes for x, y
    x = attrs.get("x")
    y = attrs.get("y")
    if x is not None and y is not None:
        try:
            return float(x), float(y)
        except (ValueError, TypeError):
            pass
    
    # Check node attributes for lat, lng (alternative naming)
    lat = attrs.get("lat")
    lng = attrs.get("lng")
    if lat is not None and lng is not None:
        try:
            return float(lng), float(lat)  # Return as (x, y) or (lng, lat)
        except (ValueError, TypeError):
            pass
    
    return None


# =========================
# PRINT VERIFICATION REPORT
# =========================
def print_verification_report(
    G: nx.Graph,
    problematic_edges: List,
    invalid_nodes: List,
    fixed_weight_count: int,
    vertical_count: int
) -> None:
    """
    Print comprehensive verification report.
    """
    node_distribution = get_node_type_distribution(G)
    edge_distribution = get_edge_type_distribution(G)
    edge_stats = calculate_edge_statistics(G)
    
    print("\n" + "="*70)
    print("GRAPH VERIFICATION REPORT")
    print("="*70)
    
    # Basic Stats
    print(f"\n📊 GRAPH STATISTICS:")
    print(f"  Total Nodes:     {G.number_of_nodes()}")
    print(f"  Total Edges:     {G.number_of_edges()}")
    print(f"  Is Connected:    {nx.is_connected(G)}")
    print(f"  Connected Components: {nx.number_connected_components(G)}")
    
    # Node Type Distribution
    print(f"\n📍 NODE TYPE DISTRIBUTION:")
    for node_type, count in sorted(node_distribution.items()):
        print(f"  {node_type:15s}: {count:4d} nodes")
    
    # Edge Type Distribution
    print(f"\n🔗 EDGE TYPE DISTRIBUTION:")
    for edge_type, count in sorted(edge_distribution.items()):
        print(f"  {edge_type:15s}: {count:4d} edges")
    
    # Edge Weight Statistics
    print(f"\n⚖️  EDGE WEIGHT STATISTICS:")
    if edge_stats["count"] > 0:
        print(f"  Valid Edges:     {edge_stats['count']}")
        print(f"  Min Weight:      {edge_stats['min']:.6f}")
        print(f"  Max Weight:      {edge_stats['max']:.6f}")
        print(f"  Avg Weight:      {edge_stats['avg']:.6f}")
        print(f"  Median Weight:   {edge_stats['median']:.6f}")
        print(f"  Std Dev:         {edge_stats['std_dev']:.6f}")
    else:
        print(f"  No valid edges found!")
    
    # Vertical Movement
    print(f"\n🔼 VERTICAL MOVEMENT:")
    print(f"  Vertical Edges:  {vertical_count}")
    
    # Verification Results
    print(f"\n✅ VERIFICATION RESULTS:")
    print(f"  Fixed Edges (missing weights): {fixed_weight_count}")
    print(f"  Invalid Nodes (no coords):     {len(invalid_nodes)}")
    print(f"  Problematic Edges (zero/neg):  {len(problematic_edges)}")
    
    # Issues
    if problematic_edges:
        print(f"\n⚠️  PROBLEMATIC EDGES (zero or negative weight):")
        for u, v, weight in problematic_edges[:10]:  # Show first 10
            print(f"  Edge ({u}, {v}): weight = {weight}")
        if len(problematic_edges) > 10:
            print(f"  ... and {len(problematic_edges) - 10} more")
    
    if invalid_nodes:
        print(f"\n⚠️  INVALID NODES (missing coordinates):")
        for node in invalid_nodes[:10]:  # Show first 10
            print(f"  Node {node}")
        if len(invalid_nodes) > 10:
            print(f"  ... and {len(invalid_nodes) - 10} more")
    
    print("\n" + "="*70 + "\n")


# =========================
# MAIN VERIFICATION FUNCTION
# =========================
def verify_graph(G: nx.Graph, verbose: bool = True) -> nx.Graph:
    """
    Perform comprehensive verification on the navigation graph.
    
    Steps:
    1. Verify and fix edge weights
    2. Verify node coordinates
    3. Flag vertical movement edges
    4. Calculate statistics
    5. Print report
    
    Args:
        G: NetworkX graph to verify
        verbose: Whether to print the report
    
    Returns:
        Cleaned and verified graph with added attributes
    """
    # Step 1: Verify edge weights
    problematic_edges, fixed_weight_count = verify_edge_weights(G)
    
    # Step 2: Verify node coordinates
    invalid_nodes, _ = verify_node_coordinates(G)
    
    # Step 3: Flag vertical movement edges
    vertical_count = flag_vertical_movement_edges(G)
    
    # Step 4: Print report if verbose
    if verbose:
        print_verification_report(
            G,
            problematic_edges,
            invalid_nodes,
            fixed_weight_count,
            vertical_count
        )
    
    return G


def load_graph_from_geojson(path: str) -> nx.Graph:
    """Load step2-exported graph GeoJSON into a NetworkX graph."""
    with open(path, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    G = nx.Graph()

    for feature in geojson_data.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})

        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) < 2:
                continue
            G.add_node(
                (coords[0], coords[1]),
                node_id=props.get("node_id"),
                type=props.get("node_type"),
                name=props.get("name"),
                space_type=props.get("space_type"),
            )

        elif geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
            if len(coords) < 2:
                continue

            u = (coords[0][0], coords[0][1])
            v = (coords[1][0], coords[1][1])
            G.add_edge(
                u,
                v,
                edge_type=props.get("edge_type"),
                weight=props.get("weight"),
            )

    return G


def export_verified_graph_to_geojson(G: nx.Graph, output_path: str):
    """Export verified graph with `is_vertical` and verified weights."""
    features = []
    node_id_map = {}

    next_node_id = 1
    for node, attrs in G.nodes(data=True):
        coords = _extract_node_coordinates(node, attrs)
        if coords is None:
            continue

        node_id_map[node] = next_node_id
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [coords[0], coords[1]],
                },
                "properties": {
                    "node_id": next_node_id,
                    "node_type": attrs.get("type"),
                    "name": attrs.get("name"),
                    "space_type": attrs.get("space_type"),
                },
            }
        )
        next_node_id += 1

    next_edge_id = 1
    for u, v, attrs in G.edges(data=True):
        if u not in node_id_map or v not in node_id_map:
            continue

        u_coords = _extract_node_coordinates(u, G.nodes[u])
        v_coords = _extract_node_coordinates(v, G.nodes[v])
        if u_coords is None or v_coords is None:
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [u_coords[0], u_coords[1]],
                        [v_coords[0], v_coords[1]],
                    ],
                },
                "properties": {
                    "edge_id": next_edge_id,
                    "source": node_id_map[u],
                    "target": node_id_map[v],
                    "edge_type": attrs.get("edge_type"),
                    "weight": attrs.get("weight"),
                    "is_vertical": attrs.get("is_vertical", False),
                },
            }
        )
        next_edge_id += 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)


# =========================
# MAIN INTEGRATION WITH PIPELINE
# =========================
def main():
    """
    Standalone execution for Step 3.
    Loads graph from step2 output and verifies it.
    """
    print("Loading navigation graph from step2...")
    G = load_graph_from_geojson("navigation_graph_export.geojson")

    # Run verification
    G = verify_graph(G, verbose=True)

    # Persist verified graph snapshot for step4
    export_verified_graph_to_geojson(G, "navigation_graph_verified.geojson")

    print(f"✓ Graph verification complete. {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")


if __name__ == "__main__":
    main()
