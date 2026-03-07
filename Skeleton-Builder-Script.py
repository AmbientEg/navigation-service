import json
import networkx as nx
from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import split, linemerge
import numpy as np

# =========================
# GLOBAL SETTINGS
# =========================
PRECISION = 8  # adjust if needed

def snap(coord):
    return (round(coord[0], PRECISION), round(coord[1], PRECISION))

# =========================
# LOAD GEOJSON DATA
# =========================
def load_geojson(file_path):
    with open(file_path) as f:
        data = json.load(f)
    return data

# =========================
# CLASSIFY FEATURES
# =========================
def classify_features(data):
    corridor_lines = []
    doors = []
    vertical_connectors = []
    rooms = []
    walls = []

    for feature in data["features"]:
        geom = shape(feature["geometry"])
        props = feature["properties"]
        stype = props.get("space_type")

        if stype == "corridor" and geom.geom_type == "LineString":
            corridor_lines.append((geom, props))
        elif stype == "door" and geom.geom_type == "LineString":
            doors.append((geom, props))
        elif stype in ["stairs", "elevator", "entrance"] and geom.geom_type == "LineString":
            vertical_connectors.append((geom, props))
        elif stype == "wall":
            walls.append(geom)
        elif geom.geom_type == "Polygon" and stype not in ["corridor", "wall", "stairs", "elevator", "entrance"]:
            rooms.append((geom, props))

    # Treat vertical connectors like doors
    doors.extend(vertical_connectors)

    print("Classification complete")
    print("Corridor lines:", len(corridor_lines))
    print("Doors + connectors:", len(doors))
    print("Rooms:", len(rooms))

    return corridor_lines, doors, rooms, walls

# =========================
# BUILD CORRIDOR BACKBONE
# =========================
def build_corridor_backbone(G, corridor_lines):
    for line, props in corridor_lines:
        coords = list(line.coords)
        # Snap all points to fixed precision
        snapped_coords = [snap(c) for c in coords]
        for i in range(len(snapped_coords) - 1):
            p1, p2 = snapped_coords[i], snapped_coords[i + 1]
            G.add_node(p1, type="corridor")
            G.add_node(p2, type="corridor")
            G.add_edge(p1, p2, weight=Point(p1).distance(Point(p2)), edge_type="corridor")
    print("Corridor backbone built")

# =========================
# ATTACH DOORS TO CORRIDOR
# =========================
def attach_doors(G, doors, corridor_lines):
    for door_geom, door_props in doors:
        # Use midpoint of door as reference
        door_point = door_geom.interpolate(0.5, normalized=True)
        best_line = min(corridor_lines, key=lambda x: x[0].distance(door_point), default=None)
        if not best_line:
            continue
        line = best_line[0]
        projected_point = line.interpolate(line.project(door_point))
        proj_coords = snap((projected_point.x, projected_point.y))

        # Add corridor projection node if not exists
        G.add_node(proj_coords, type="corridor")

        # Split corridor at projection point
        split_result = split(line, projected_point)
        if len(split_result.geoms) > 1:
            for segment in split_result.geoms:
                segment_coords = [snap(c) for c in segment.coords]
                if len(segment_coords) >= 2:
                    G.add_edge(segment_coords[0], segment_coords[-1],
                               weight=Point(segment_coords[0]).distance(Point(segment_coords[-1])),
                               edge_type="corridor")

        # Add door node and connect
        door_coords = snap((door_point.x, door_point.y))
        G.add_node(door_coords, type="door",
                   name=door_props.get("name"),
                   routing_cost=door_props.get("routing_cost", 1))
        G.add_edge(proj_coords, door_coords,
                   weight=projected_point.distance(door_point),
                   edge_type="door")
    print("Doors attached with edge splitting")

# =========================
# ATTACH ROOMS TO DOORS
# =========================
def attach_rooms(G, rooms):
    door_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "door"]
    for room_geom, room_props in rooms:
        room_center = room_geom.centroid
        room_coords = snap((room_center.x, room_center.y))
        G.add_node(room_coords,
                   type="room",
                   name=room_props.get("name"),
                   space_type=room_props.get("space_type"))
        if door_nodes:
            nearest_door = min(door_nodes, key=lambda n: Point(n).distance(room_center))
            G.add_edge(nearest_door, room_coords,
                       weight=Point(nearest_door).distance(room_center),
                       edge_type="room_connection")
    print("Rooms attached")

# =========================
# SNAP JUNCTION NODES
# =========================
def snap_junctions(G):
    """
    For all corridor edges, detect intersections and snap nodes at junctions.
    Ensures that existing edges are split and new nodes are created at intersections.
    """
    corridor_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "corridor"]
    lines = [(u, v, LineString([u, v])) for u, v in corridor_edges]
    new_nodes = []

    for i, (u1, v1, line1) in enumerate(lines):
        for j, (u2, v2, line2) in enumerate(lines):
            if i >= j:
                continue
            if line1.intersects(line2):
                inter = line1.intersection(line2)
                if inter.geom_type == "Point":
                    snap_pt = snap((inter.x, inter.y))
                    if snap_pt not in G.nodes:
                        G.add_node(snap_pt, type="corridor")
                        new_nodes.append(snap_pt)

                    # Replace edges with split edges
                    def split_edge(a, b, pt):
                        if a != pt and b != pt:
                            if G.has_edge(a, b):
                                G.remove_edge(a, b)
                            G.add_edge(a, pt, weight=Point(a).distance(Point(pt)), edge_type="corridor")
                            G.add_edge(pt, b, weight=Point(pt).distance(Point(b)), edge_type="corridor")

                    split_edge(u1, v1, snap_pt)
                    split_edge(u2, v2, snap_pt)

    print(f"Junction snapping done. Added {len(new_nodes)} nodes at intersections.")

# =========================
# EXPORT GRAPH TO GEOJSON
# =========================
def export_graph(G, output_file="navigation_graph.geojson"):
    features = []
    node_id_map = {node: idx+1 for idx, node in enumerate(G.nodes)}

    for node, attrs in G.nodes(data=True):
        features.append({
            "type": "Feature",
            "geometry": mapping(Point(node)),
            "properties": {
                "feature_type": "node",
                "node_id": node_id_map[node],
                "node_type": attrs.get("type"),
                "name": attrs.get("name"),
                "space_type": attrs.get("space_type")
            }
        })

    for idx, (u, v, attrs) in enumerate(G.edges(data=True), 1):
        features.append({
            "type": "Feature",
            "geometry": mapping(LineString([u, v])),
            "properties": {
                "feature_type": "edge",
                "edge_id": idx,
                "source": node_id_map[u],
                "target": node_id_map[v],
                "edge_type": attrs.get("edge_type"),
                "weight": attrs.get("weight")
            }
        })

    with open(output_file, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)

    print(f"{output_file} exported with IDs")
    print("Total Nodes:", len(G.nodes))
    print("Total Edges:", len(G.edges))

# =========================
# CHECK GRAPH CONNECTIVITY
# =========================
def check_connectivity(G):
    print("Is graph connected:", nx.is_connected(G))
    print("Connected components:", len(list(nx.connected_components(G))))

# =========================
# MAIN EXECUTION
# =========================
def main():
    G = nx.Graph()
    data = load_geojson("floor3.geojson")
    corridor_lines, doors, rooms, walls = classify_features(data)
    build_corridor_backbone(G, corridor_lines)
    attach_doors(G, doors, corridor_lines)
    attach_rooms(G, rooms)
    snap_junctions(G)
    export_graph(G)
    check_connectivity(G)

if __name__ == "__main__":
    main()