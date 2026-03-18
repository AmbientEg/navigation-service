import json
import networkx as nx
from shapely.geometry import shape, Point, LineString, mapping
import matplotlib.pyplot as plt

INPUT_FILE = "floor3_updated.geojson"
OUTPUT_FILE = "navigation_graph.geojson"


# =========================
# LOAD GEOJSON
# =========================

def load_geojson(path):
    with open(path) as f:
        return json.load(f)


# =========================
# CLASSIFY FEATURES
# =========================

def classify_features(data):

    corridors = []
    doors = []
    rooms = []

    for feature in data["features"]:

        geom = shape(feature["geometry"])
        props = feature["properties"]
        stype = props.get("space_type")

        if stype == "corridor" and geom.geom_type == "LineString":
            corridors.append((geom, props))

        elif stype == "door" and geom.geom_type == "LineString":
            doors.append((geom, props))

        elif geom.geom_type == "Polygon" and stype not in ["corridor", "wall"]:
            rooms.append((geom, props))

    return corridors, doors, rooms


# =========================
# BUILD CORRIDOR SKELETON
# =========================

def build_corridor_skeleton(corridors):

    G = nx.Graph()

    for line, props in corridors:

        coords = list(line.coords)

        for i in range(len(coords)-1):

            p1 = tuple(coords[i])
            p2 = tuple(coords[i+1])

            G.add_node(p1, type="corridor")
            G.add_node(p2, type="corridor")

            dist = Point(p1).distance(Point(p2))

            G.add_edge(
                p1,
                p2,
                weight=dist,
                edge_type="corridor"
            )

    return G


# =========================
# SPLIT CORRIDOR INTERSECTIONS
# =========================

def split_corridor_intersections(G):

    edges = list(G.edges())

    for i, (u1, v1) in enumerate(edges):

        line1 = LineString([u1, v1])

        for u2, v2 in edges[i+1:]:

            line2 = LineString([u2, v2])

            if line1.intersects(line2):

                inter = line1.intersection(line2)

                if inter.geom_type == "Point":

                    pt = (inter.x, inter.y)

                    G.add_node(pt, type="junction")

                    if G.has_edge(u1, v1):
                        G.remove_edge(u1, v1)

                        G.add_edge(u1, pt, weight=Point(u1).distance(inter), edge_type="corridor")
                        G.add_edge(pt, v1, weight=Point(v1).distance(inter), edge_type="corridor")

                    if G.has_edge(u2, v2):
                        G.remove_edge(u2, v2)

                        G.add_edge(u2, pt, weight=Point(u2).distance(inter), edge_type="corridor")
                        G.add_edge(pt, v2, weight=Point(v2).distance(inter), edge_type="corridor")


# =========================
# PROJECT DOORS TO CORRIDORS
# =========================

def project_doors_to_corridors(G, corridors, doors):

    corridor_lines = [line for line, _ in corridors]

    for door_geom, props in doors:

        midpoint = door_geom.interpolate(0.5, normalized=True)

        nearest = min(
            corridor_lines,
            key=lambda l: l.distance(midpoint)
        )

        proj = nearest.interpolate(
            nearest.project(midpoint)
        )

        corridor_point = (proj.x, proj.y)
        door_point = (midpoint.x, midpoint.y)

        G.add_node(
            door_point,
            type="door",
            name=props.get("name")
        )

        dist = Point(door_point).distance(Point(corridor_point))

        G.add_edge(
            corridor_point,
            door_point,
            weight=dist,
            edge_type="door"
        )


# =========================
# CONNECT ROOMS TO DOORS
# =========================

def connect_rooms_to_doors(G, rooms):

    door_nodes = [
        n for n, d in G.nodes(data=True)
        if d.get("type") == "door"
    ]

    for geom, props in rooms:

        centroid = geom.centroid
        room_node = (centroid.x, centroid.y)

        G.add_node(
            room_node,
            type="room",
            name=props.get("name"),
            space_type=props.get("space_type")
        )

        nearest_door = min(
            door_nodes,
            key=lambda n: Point(n).distance(centroid)
        )

        dist = Point(nearest_door).distance(centroid)

        G.add_edge(
            nearest_door,
            room_node,
            weight=dist,
            edge_type="room_connection"
        )


# =========================
# VALIDATE CONNECTIVITY
# =========================

def validate_connectivity(G):

    print("Nodes:", G.number_of_nodes())
    print("Edges:", G.number_of_edges())

    connected = nx.is_connected(G)

    print("Connected:", connected)

    if not connected:
        print("Components:", nx.number_connected_components(G))


# =========================
# VISUALIZE GRAPH
# =========================

def visualize_graph(G):

    pos = {node: node for node in G.nodes}

    colors = []

    for _, data in G.nodes(data=True):

        t = data.get("type")

        if t == "corridor":
            colors.append("gray")

        elif t == "door":
            colors.append("blue")

        elif t == "room":
            colors.append("green")

        elif t == "junction":
            colors.append("red")

        else:
            colors.append("black")

    nx.draw(
        G,
        pos,
        node_size=30,
        node_color=colors,
        with_labels=False
    )

    plt.show()


# =========================
# EXPORT GRAPH
# =========================

def export_graph(G):

    features = []

    for u, v, data in G.edges(data=True):

        line = LineString([u, v])

        features.append({
            "type": "Feature",
            "geometry": mapping(line),
            "properties": data
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(geojson, f, indent=2)


# =========================
# MAIN PIPELINE
# =========================

def main():

    data = load_geojson(INPUT_FILE)

    corridors, doors, rooms = classify_features(data)

    G = build_corridor_skeleton(corridors)

    split_corridor_intersections(G)

    project_doors_to_corridors(G, corridors, doors)

    connect_rooms_to_doors(G, rooms)

    validate_connectivity(G)

    visualize_graph(G)

    export_graph(G)


if __name__ == "__main__":
    main()