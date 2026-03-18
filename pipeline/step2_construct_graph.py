import json
import networkx as nx
from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import split
import matplotlib.pyplot as plt

# =========================
# SETTINGS
# =========================
PRECISION = 8  # coordinate snapping precision

def snap(coord):
    return (round(coord[0], PRECISION), round(coord[1], PRECISION))

# =========================
# LOAD GEOJSON
# =========================
def load_geojson(file_path):
    with open(file_path) as f:
        return json.load(f)

# =========================
# CLASSIFY FEATURES
# =========================
def classify_features(data):
    corridor_lines, doors, rooms, walls = [], [], [], []

    for feature in data["features"]:
        geom = shape(feature["geometry"])
        stype = feature["properties"].get("space_type")

        if stype == "corridor" and geom.geom_type == "LineString":
            corridor_lines.append((geom, feature["properties"]))
        elif stype == "door" and geom.geom_type == "LineString":
            doors.append((geom, feature["properties"]))
        elif stype in ["stairs", "elevator", "entrance"] and geom.geom_type == "LineString":
            doors.append((geom, feature["properties"]))  # treat vertical connectors as doors
        elif stype == "wall":
            walls.append(geom)
        elif geom.geom_type == "Polygon" and stype not in ["corridor", "wall"]:
            rooms.append((geom, feature["properties"]))

    return corridor_lines, doors, rooms, walls

# =========================
# BUILD CORRIDOR BACKBONE
# =========================
def build_corridor_backbone(G, corridor_lines):
    for line, props in corridor_lines:
        coords = [snap(c) for c in line.coords]
        for i in range(len(coords) - 1):
            p1, p2 = coords[i], coords[i + 1]
            G.add_node(p1, type="corridor")
            G.add_node(p2, type="corridor")
            G.add_edge(p1, p2, weight=Point(p1).distance(Point(p2)), edge_type="corridor")

# =========================
# ADD JUNCTIONS (DECISION POINTS)
# =========================
def add_junctions(G):
    corridor_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "corridor"]
    for i, (u1, v1) in enumerate(corridor_edges):
        line1 = LineString([u1, v1])
        for u2, v2 in corridor_edges[i+1:]:
            line2 = LineString([u2, v2])
            if line1.intersects(line2):
                inter = line1.intersection(line2)
                if inter.geom_type == "Point":
                    pt = snap((inter.x, inter.y))
                    G.add_node(pt, type="junction")
                    # Split first edge
                    if G.has_edge(u1, v1):
                        G.remove_edge(u1, v1)
                        G.add_edge(u1, pt, weight=Point(u1).distance(Point(pt)), edge_type="corridor")
                        G.add_edge(pt, v1, weight=Point(pt).distance(Point(v1)), edge_type="corridor")
                    # Split second edge
                    if G.has_edge(u2, v2):
                        G.remove_edge(u2, v2)
                        G.add_edge(u2, pt, weight=Point(u2).distance(Point(pt)), edge_type="corridor")
                        G.add_edge(pt, v2, weight=Point(pt).distance(Point(v2)), edge_type="corridor")

# =========================
# ATTACH DOORS
# =========================
def attach_doors(G, doors):
    for door_geom, props in doors:
        corridor_edges = [
            (u, v) for u, v, d in G.edges(data=True)
            if d.get("edge_type") == "corridor"
        ]

        mid = door_geom.interpolate(0.5, normalized=True)
        door_coord = snap((mid.x, mid.y))

        best_edge = None
        best_proj = None
        best_dist = float("inf")

        for u, v in corridor_edges:
            line = LineString([u, v])
            proj_dist = line.project(mid)
            proj_point = line.interpolate(proj_dist)
            dist = proj_point.distance(mid)

            if dist < best_dist:
                best_dist = dist
                best_proj = proj_point
                best_edge = (u, v)

        if best_edge is None:
            continue

        proj_coord = snap((best_proj.x, best_proj.y))
        u, v = best_edge

        if G.has_edge(u, v):
            G.remove_edge(u, v)
            G.add_node(proj_coord, type="corridor")
            G.add_edge(u, proj_coord, weight=Point(u).distance(Point(proj_coord)), edge_type="corridor")
            G.add_edge(proj_coord, v, weight=Point(proj_coord).distance(Point(v)), edge_type="corridor")

        G.add_node(door_coord, type="door", name=props.get("name"))
        G.add_edge(
            proj_coord,
            door_coord,
            weight=Point(proj_coord).distance(Point(door_coord)),
            edge_type="door"
        )

# =========================
# ATTACH ROOMS
# =========================
def attach_rooms(G, rooms):
    door_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "door"]
    for geom, props in rooms:
        center = snap((geom.centroid.x, geom.centroid.y))
        G.add_node(center, type="room", name=props.get("name"), space_type=props.get("space_type"))
        if door_nodes:
            nearest_door = min(door_nodes, key=lambda n: Point(n).distance(Point(center)))
            G.add_edge(nearest_door, center, weight=Point(nearest_door).distance(Point(center)), edge_type="room_connection")

# =========================
# CHECK CONNECTIVITY
# =========================
def check_connectivity(G):
    connected = nx.is_connected(G)
    print("Graph connected:", connected)
    components = list(nx.connected_components(G))
    print("Number of connected components:", len(components))
    for i, component in enumerate(components, start=1):
        print(f"\n  Component {i} — {len(component)} node(s):")
        for node in sorted(component):
            attrs = G.nodes[node]
            node_type = attrs.get("type", "unknown")
            name = attrs.get("name")
            label = f"    Node {node}  |  type={node_type}"
            if name:
                label += f"  |  name={name}"
            print(label)

# =========================
# VISUALIZE
# =========================
def visualize_graph(G):
    pos = {n: n for n in G.nodes}

    # Separate nodes by type
    type_config = {
        "corridor":   {"color": "gray",   "size": 50,  "shape": "o"},
        "door":       {"color": "blue",   "size": 50,  "shape": "o"},
        "room":       {"color": "green",  "size": 50,  "shape": "o"},
        "junction":   {"color": "red",    "size": 50,  "shape": "o"},
    }
    unknown_config = {"color": "orange", "size": 150, "shape": "*"}

    fig, ax = plt.subplots()

    # Draw edges
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="lightgray", width=1)

    # Draw known-type nodes grouped by type
    grouped = {}
    for n, d in G.nodes(data=True):
        t = d.get("type") if d.get("type") in type_config else None
        grouped.setdefault(t, []).append(n)

    for t, nodes in grouped.items():
        if t is None:
            continue
        cfg = type_config[t]
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=nodes,
            node_color=cfg["color"],
            node_size=cfg["size"],
            node_shape=cfg["shape"],
            ax=ax,
        )

    # Draw unknown nodes with star shape, triple size
    unknown_nodes = grouped.get(None, [])
    if unknown_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=unknown_nodes,
            node_color=unknown_config["color"],
            node_size=unknown_config["size"],
            node_shape=unknown_config["shape"],
            ax=ax,
            label="unknown",
        )

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="gray",  markersize=6, label="corridor"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="blue",  markersize=6, label="door"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="green", markersize=6, label="room"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="red",   markersize=6, label="junction"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor="orange", markersize=10, label="unknown"),
    ]
    ax.legend(handles=legend_elements, loc="best", fontsize=8)
    ax.set_title("Navigation Graph")
    plt.axis("equal")
    plt.tight_layout()
    plt.show()

# =========================
# EXPORT GRAPH TO GEOJSON
# =========================
def _extract_node_coordinates(node, attrs):
    """
    Resolve node coordinates safely.
    Supports:
      - tuple/list node keys like (x, y)
      - node attributes containing x/y
    Returns (x, y) or None if coordinates cannot be resolved.
    """
    if isinstance(node, (tuple, list)) and len(node) >= 2:
        return float(node[0]), float(node[1])

    x = attrs.get("x")
    y = attrs.get("y")
    if x is not None and y is not None:
        return float(x), float(y)

    return None


def export_graph(G, output_file):
    """
    Export a NetworkX graph to GeoJSON.

    - Nodes are exported as Point features with properties:
      node_id, node_type, name, space_type
    - Edges are exported as LineString features with properties:
      edge_id, source, target, edge_type, weight

    Notes:
      - node_id and edge_id are unique incremental integers starting from 1.
      - Missing optional attributes are written as null.
      - Nodes without resolvable coordinates are skipped (and so are related edges).
    """
    features = []
    node_id_map = {}

    # Assign incremental node IDs and export node features
    next_node_id = 1
    for node, attrs in G.nodes(data=True):
        coords = _extract_node_coordinates(node, attrs)
        if coords is None:
            continue

        node_id_map[node] = next_node_id
        x, y = coords

        node_feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [x, y]
            },
            "properties": {
                "node_id": next_node_id,
                "node_type": attrs.get("type"),
                "name": attrs.get("name"),
                "space_type": attrs.get("space_type")
            }
        }
        features.append(node_feature)
        next_node_id += 1

    # Assign incremental edge IDs and export edge features
    next_edge_id = 1
    for u, v, attrs in G.edges(data=True):
        # Skip edges whose endpoints were not exported
        if u not in node_id_map or v not in node_id_map:
            continue

        u_coords = _extract_node_coordinates(u, G.nodes[u])
        v_coords = _extract_node_coordinates(v, G.nodes[v])
        if u_coords is None or v_coords is None:
            continue

        edge_feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [u_coords[0], u_coords[1]],
                    [v_coords[0], v_coords[1]]
                ]
            },
            "properties": {
                "edge_id": next_edge_id,
                "source": node_id_map[u],
                "target": node_id_map[v],
                "edge_type": attrs.get("edge_type"),
                "weight": attrs.get("weight")
            }
        }
        features.append(edge_feature)
        next_edge_id += 1

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

# =========================
# clean up graph by removing self-loops and zero-length edges
# =========================

def remove_self_loops(G):
    loops = list(nx.selfloop_edges(G))

    if loops:
        print(f"\nRemoving {len(loops)} self-loop edges")
        for u, v in loops:
            print(f"  Removing loop at {u}")

        G.remove_edges_from(loops)


def remove_zero_length_edges(G, threshold=1e-9):
    to_remove = []

    for u, v, d in G.edges(data=True):
        if d.get("weight", 0) < threshold:
            to_remove.append((u, v))

    if to_remove:
        print(f"Removing {len(to_remove)} zero-length edges")
        G.remove_edges_from(to_remove)

# =========================
# MAIN
# =========================
def main():
    G = nx.Graph()
    data = load_geojson("floor3_centerlines.geojson")
    corridor_lines, doors, rooms, walls = classify_features(data)
    build_corridor_backbone(G, corridor_lines)
    add_junctions(G)
    attach_doors(G, doors)
    attach_rooms(G, rooms)
    remove_self_loops(G)
    remove_zero_length_edges(G)
    check_connectivity(G)
    visualize_graph(G)

    export_graph(G, "navigation_graph_export.geojson")

if __name__ == "__main__":
    main()