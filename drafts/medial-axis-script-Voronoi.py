import json
import numpy as np
import networkx as nx
from shapely.geometry import (
    shape, Polygon, MultiPolygon,
    GeometryCollection, LineString, MultiLineString
)
from shapely.ops import unary_union
from scipy.spatial import Voronoi

# =========================================================
# 1. LOAD + CLEAN CORRIDORS
# =========================================================

def load_corridors(filepath):
    with open(filepath) as f:
        data = json.load(f)

    corridors = []

    for feature in data["features"]:
        if feature["properties"].get("space_type") == "corridor":
            geom = shape(feature["geometry"])

            # Fix invalid geometries
            geom = geom.buffer(0)

            if isinstance(geom, (Polygon, MultiPolygon)):
                corridors.append(geom)

    return corridors


# =========================================================
# 2. SAFE MERGE
# =========================================================

def safe_merge(polygons):
    merged = unary_union(polygons)

    if isinstance(merged, Polygon):
        return MultiPolygon([merged])

    if isinstance(merged, MultiPolygon):
        return merged

    if isinstance(merged, GeometryCollection):
        polys = [g for g in merged.geoms if isinstance(g, Polygon)]
        return MultiPolygon(polys)

    raise ValueError("Unsupported geometry after merge")


# =========================================================
# 3. SAMPLE BOUNDARY POINTS
# =========================================================

def sample_boundary(multipolygon, spacing=0.00001):
    points = []

    for poly in multipolygon.geoms:
        boundary = poly.exterior
        length = boundary.length
        n = max(int(length / spacing), 10)

        for i in range(n):
            p = boundary.interpolate(i * spacing)
            points.append((p.x, p.y))

    return np.array(points)


# =========================================================
# 4. VORONOI CENTERLINE EXTRACTION
# =========================================================

def extract_centerlines(merged_corridor, boundary_points):
    vor = Voronoi(boundary_points)

    lines = []

    for ridge in vor.ridge_vertices:
        if -1 in ridge:
            continue

        p1 = vor.vertices[ridge[0]]
        p2 = vor.vertices[ridge[1]]

        line = LineString([p1, p2])

        # Keep only lines fully inside corridor
        if merged_corridor.contains(line):
            lines.append(line)

    return MultiLineString(lines)


# =========================================================
# 4.2. Graph Simplification + Line Fitting
# Remove degree-2 nodes (merge straight segments)
# Merge collinear edges
# Fit straight line per corridor branch
# =========================================================

def simplify_graph(G, angle_threshold=10):
    import math

    def angle(a, b, c):
        # angle at b
        ba = (a[0] - b[0], a[1] - b[1])
        bc = (c[0] - b[0], c[1] - b[1])

        dot = ba[0] * bc[0] + ba[1] * bc[1]
        mag_ba = math.hypot(*ba)
        mag_bc = math.hypot(*bc)

        if mag_ba * mag_bc == 0:
            return 180

        cos_angle = dot / (mag_ba * mag_bc)
        cos_angle = max(-1, min(1, cos_angle))
        return math.degrees(math.acos(cos_angle))

    changed = True

    while changed:
        changed = False

        for node in list(G.nodes):
            neighbors = list(G.neighbors(node))

            if len(neighbors) == 2:
                n1, n2 = neighbors

                ang = angle(n1, node, n2)

                # if almost straight
                if abs(ang - 180) < angle_threshold:
                    w1 = G[node][n1]['weight']
                    w2 = G[node][n2]['weight']

                    G.add_edge(n1, n2, weight=w1 + w2)
                    G.remove_node(node)

                    changed = True
                    break

    return G


# =========================================================
# 5. CONVERT TO GRAPH
# =========================================================

def centerlines_to_graph(centerlines):
    G = nx.Graph()

    for line in centerlines.geoms:
        coords = list(line.coords)
        start = tuple(coords[0])
        end = tuple(coords[1])
        length = line.length

        G.add_node(start)
        G.add_node(end)
        G.add_edge(start, end, weight=length)

    return G


# =========================================================
# MAIN
# =========================================================

corridors = load_corridors("floor3.geojson")

merged_corridor = safe_merge(corridors)

boundary_points = sample_boundary(merged_corridor, spacing=0.00001)

centerlines = extract_centerlines(merged_corridor, boundary_points)

G = centerlines_to_graph(centerlines)


print("Nodes:", len(G.nodes))
print("Edges:", len(G.edges))





import matplotlib.pyplot as plt

def visualize(merged_corridor, centerlines, G):
    plt.figure(figsize=(8, 8))

    # ---- Plot corridor polygons ----
    for poly in merged_corridor.geoms:
        x, y = poly.exterior.xy
        plt.plot(x, y)

    # ---- Plot centerlines ----
    for line in centerlines.geoms:
        x, y = line.xy
        plt.plot(x, y)

    # ---- Plot graph nodes ----
    xs = [node[0] for node in G.nodes]
    ys = [node[1] for node in G.nodes]
    plt.scatter(xs, ys)

    plt.title("Voronoi Centerlines")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.gca().set_aspect("equal", adjustable="box")
    plt.show()


# Call it
visualize(merged_corridor, centerlines, G)