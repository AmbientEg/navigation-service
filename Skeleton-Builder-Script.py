import json
import networkx as nx
from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import split

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
        for i in range(len(coords) - 1):
            p1 = snap(coords[i])
            p2 = snap(coords[i + 1])

            G.add_node(p1, type="corridor")
            G.add_node(p2, type="corridor")
            G.add_edge(
                p1,
                p2,
                weight=Point(p1).distance(Point(p2)),
                edge_type="corridor"
            )
    print("Corridor backbone built")

# =========================
# ATTACH DOORS TO CORRIDOR
# =========================
def attach_doors(G, doors, corridor_lines):
    for door_geom, door_props in doors:
        door_point = door_geom.interpolate(0.5, normalized=True)

        # Find nearest corridor centerline
        best_line = None
        min_distance = float("inf")
        for line, _ in corridor_lines:
            dist = line.distance(door_point)
            if dist < min_distance:
                min_distance = dist
                best_line = line
        if not best_line:
            continue

        projected_distance = best_line.project(door_point)
        projected_point = best_line.interpolate(projected_distance)
        proj_coords = (projected_point.x, projected_point.y)

        G.add_node(proj_coords, type="corridor")

        # Split corridor line at projection point
        split_result = split(best_line, projected_point)
        if len(split_result.geoms) == 2:
            for segment in split_result.geoms:
                coords = list(segment.coords)
                p1 = snap(coords[0])
                p2 = snap(coords[-1])
                G.add_node(p1, type="corridor")
                G.add_node(p2, type="corridor")
                G.add_edge(
                    p1,
                    p2,
                    weight=Point(p1).distance(Point(p2)),
                    edge_type="corridor"
                )

        # Add door node and connect
        door_coords = (door_point.x, door_point.y)
        G.add_node(
            door_coords,
            type="door",
            name=door_props.get("name"),
            routing_cost=door_props.get("routing_cost", 1)
        )
        G.add_edge(
            proj_coords,
            door_coords,
            weight=projected_point.distance(door_point),
            edge_type="door"
        )
    print("Doors attached with edge splitting")

# =========================
# ATTACH ROOMS TO DOORS
# =========================
def attach_rooms(G, rooms):
    door_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "door"]
    for room_geom, room_props in rooms:
        room_center = room_geom.centroid
        room_coords = (room_center.x, room_center.y)
        G.add_node(
            room_coords,
            type="room",
            name=room_props.get("name"),
            space_type=room_props.get("space_type")
        )
        if door_nodes:
            nearest_door = min(door_nodes, key=lambda n: Point(n).distance(room_center))
            G.add_edge(
                nearest_door,
                room_coords,
                weight=Point(nearest_door).distance(room_center),
                edge_type="room_connection"
            )
    print("Rooms attached")

# =========================
# EXPORT GRAPH TO GEOJSON
# =========================
def export_graph(G, output_file="navigation_graph.geojson"):
    features = []
    node_id_map = {}
    node_counter = 1

    for node in G.nodes():
        node_id_map[node] = node_counter
        node_counter += 1

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

    edge_counter = 1
    for u, v, attrs in G.edges(data=True):
        features.append({
            "type": "Feature",
            "geometry": mapping(LineString([u, v])),
            "properties": {
                "feature_type": "edge",
                "edge_id": edge_counter,
                "source": node_id_map[u],
                "target": node_id_map[v],
                "edge_type": attrs.get("edge_type"),
                "weight": attrs.get("weight")
            }
        })
        edge_counter += 1

    output = {
        "type": "FeatureCollection",
        "features": features
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"{output_file} exported with IDs")
    print("Total Nodes:", len(G.nodes))
    print("Total Edges:", len(G.edges))

# =========================
# CHECK GRAPH CONNECTIVITY
# =========================
def check_connectivity(G):
    print("Is graph connected:", nx.is_connected(G))
    components = list(nx.connected_components(G))
    print("Connected components:", len(components))

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
    export_graph(G)
    check_connectivity(G)

if __name__ == "__main__":
    main()