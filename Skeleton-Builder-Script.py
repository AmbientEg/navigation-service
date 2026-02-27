import json
import networkx as nx
from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import split

# =========================
# LOAD DATA
# =========================
with open("floor3.geojson") as f:
    data = json.load(f)

G = nx.Graph()

corridor_lines = []
doors = []
vertical_connectors = []
rooms = []
walls = []

# =========================
# GLOBAL PRECISION CONTROL to normalize the coordinates and eliminate duplicates
# =========================
PRECISION = 8  # adjust if needed

def snap(coord):
    return (round(coord[0], PRECISION), round(coord[1], PRECISION))

# =========================
# CLASSIFY FEATURES (STRICT space_type)
# =========================
for feature in data["features"]:
    geom = shape(feature["geometry"])
    props = feature["properties"]
    stype = props.get("space_type")

    # Corridor backbone (centerlines only)
    if stype == "corridor" and geom.geom_type == "LineString":
        corridor_lines.append((geom, props))

    # Doors
    elif stype == "door" and geom.geom_type == "LineString":
        doors.append((geom, props))

    # Vertical connectors (stairs/elevator access lines)
    elif stype in ["stairs", "elevator", "entrance"] and geom.geom_type == "LineString":
        vertical_connectors.append((geom, props))

    # Walls (obstacles only, not added to graph)
    elif stype == "wall":
        walls.append(geom)

    # Destination spaces (all polygons except corridor & wall)
    elif (
            geom.geom_type == "Polygon"
            and stype not in ["corridor", "wall", "stairs", "elevator", "entrance"]
    ):
        rooms.append((geom, props))

# Treat vertical connectors like doors
doors.extend(vertical_connectors)

print("Classification complete")
print("Corridor lines:", len(corridor_lines))
print("Doors + connectors:", len(doors))
print("Rooms:", len(rooms))

# =========================
# BUILD CORRIDOR BACKBONE
# =========================
for line, props in corridor_lines:
    coords = list(line.coords)

    for i in range(len(coords) - 1):
        p1 = snap(tuple(coords[i]))
        p2 = snap(tuple(coords[i + 1]))

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
# ATTACH DOORS (EDGE PROJECTION + SPLIT)
# =========================
for door_geom, door_props in doors:

    #door_center = door_geom.centroid
    #door_point = Point(door_center.x, door_center.y)
    door_point = door_geom.interpolate(0.5, normalized=True)

    best_line = None
    min_distance = float("inf")

    # Find nearest corridor centerline
    for line, _ in corridor_lines:
        dist = line.distance(door_point)
        if dist < min_distance:
            min_distance = dist
            best_line = line

    if not best_line:
        continue

    # Project door onto corridor line
    projected_distance = best_line.project(door_point)
    projected_point = best_line.interpolate(projected_distance)
    proj_coords = (projected_point.x, projected_point.y)

    # Add projection node
    G.add_node(proj_coords, type="corridor")

    # Remove original edge before splitting
    # coords = list(best_line.coords)
    # for i in range(len(coords) - 1):
    #     p1 = snap(tuple(coords[i]))
    #     p2 = snap(tuple(coords[i + 1]))
    #     if G.has_edge(p1, p2):
    #         G.remove_edge(p1, p2)

    # Split corridor line at projection point
    split_result = split(best_line, projected_point)

    if len(split_result.geoms) == 2:
        for segment in split_result.geoms:
            coords = list(segment.coords)
            p1 = snap(tuple(coords[0]))
            p2 = snap(tuple(coords[-1]))

            G.add_node(p1, type="corridor")
            G.add_node(p2, type="corridor")

            G.add_edge(
                p1,
                p2,
                weight=Point(p1).distance(Point(p2)),
                edge_type="corridor"
            )

    # Add door node
    door_coords = (door_point.x, door_point.y)

    G.add_node(
        door_coords,
        type="door",
        name=door_props.get("name"),
        routing_cost=door_props.get("routing_cost", 1)
    )

    # Connect door to corridor
    G.add_edge(
        proj_coords,
        door_coords,
        weight=projected_point.distance(door_point),
        edge_type="door"
    )

print("Doors attached with edge splitting")

# =========================
# ATTACH ROOMS TO NEAREST DOOR
# =========================
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
        nearest_door = min(
            door_nodes,
            key=lambda n: Point(n).distance(room_center)
        )

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
features = []

# Export nodes
for node, attrs in G.nodes(data=True):
    features.append({
        "type": "Feature",
        "geometry": mapping(Point(node)),
        "properties": {
            "feature_type": "node",
            "node_type": attrs.get("type"),
            "name": attrs.get("name"),
            "space_type": attrs.get("space_type")
        }
    })

# Export edges
for u, v, attrs in G.edges(data=True):
    features.append({
        "type": "Feature",
        "geometry": mapping(LineString([u, v])),
        "properties": {
            "feature_type": "edge",
            "edge_type": attrs.get("edge_type"),
            "weight": attrs.get("weight")
        }
    })

output = {
    "type": "FeatureCollection",
    "features": features
}

with open("navigation_graph.geojson", "w") as f:
    json.dump(output, f, indent=2)

print("navigation_graph.geojson exported")
print("Total Nodes:", len(G.nodes))
print("Total Edges:", len(G.edges))