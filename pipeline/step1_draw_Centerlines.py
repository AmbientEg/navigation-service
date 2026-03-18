import json
from abc import ABC, abstractmethod
from shapely.geometry import shape, Polygon, LineString, mapping
import networkx as nx
from shapely.geometry.point import Point


# create a class using strategy pattern
# =========================
# STRATEGY INTERFACE
# =========================
class CenterLineStrategy(ABC):
    @abstractmethod
    def draw(self, polygon: Polygon) -> list[LineString]:
        pass

# class draw center line

# =========================
# CONCRETE STRATEGIES
# =========================

# implement strategy for T corridor

    # for the _|_ polygon should we handel it like T ??
    # for _|_
    # construct 2 lines
    # polygon  _|_  is represented as 9 points , 1 and 9 are the same
    # line 1 --> start middle of point 4 and 5, and end middle of point 6 and 7
    # line 2 --> start middle of point 1 and 2, and end ??
    # end is trickey for line 2 if the end is represented as (x,y ) pair , we have the x but we need the y
    # we will calc the Y from "middle of point 4 and 5" or "middle of point 6 and 7"

class TCorridorStrategy(CenterLineStrategy):
    """Handles _|_ shaped polygons (8-9 points)"""

    def draw(self, polygon: Polygon) -> list[LineString]:
        coords = list(polygon.exterior.coords)[:-1]

        # Line 1 (Horizontal bar): Midpoint of 1-based (4,5) and (6,7)
        # Python 0-based: (3,4) and (5,6)
        m45_adj = LineString([coords[3], coords[4]]).interpolate(0.5, normalized=True)
        m67_adj = LineString([coords[5], coords[6]]).interpolate(0.5, normalized=True)
        line1 = LineString([m45_adj, m67_adj])

        # Line 2 (Stem): Midpoint of 1-based (1,2) to intersection
        # Python 0-based: (0,1)
        m12_adj = LineString([coords[0], coords[1]]).interpolate(0.5, normalized=True)

        # Use projection to find the exact junction on Line 1
        # bug this junction projection make the line 2 not straight it has a degree of shift
        proj_dist = line1.project(m12_adj)
        intersection_pt = line1.interpolate(proj_dist)

        line2 = LineString([m12_adj, intersection_pt])
        return [line1, line2]

# implement strategy for L corridor

class LCorridorStrategy(CenterLineStrategy):
    """Handles elbow joints (6 points)"""
    def draw(self, polygon: Polygon) -> list[LineString]:
        coords = list(polygon.exterior.coords)[:-1]
        # 1-based (1,2) and (4,5) are end caps
        m_start = LineString([coords[0], coords[1]]).interpolate(0.5, normalized=True)
        m_end = LineString([coords[3], coords[4]]).interpolate(0.5, normalized=True)
        # Junction point (center of the elbow)
        corner = LineString([coords[2], coords[5]]).interpolate(0.5, normalized=True)
        return [LineString([m_start, corner]), LineString([corner, m_end])]

# implement strategy for | corridor

class ICorridorStrategy(CenterLineStrategy):
    """Handles simple rectangular corridors (4-5 points)"""

    def draw(self, polygon: Polygon) -> list[LineString]:
        coords = list(polygon.exterior.coords)[:-1]
        # Midpoints of opposite sides
        m1 = LineString([coords[0], coords[1]]).interpolate(0.5, normalized=True)
        m2 = LineString([coords[2], coords[3]]).interpolate(0.5, normalized=True)

        d1 = Point(coords[0]).distance(Point(coords[1]))
        d2 = Point(coords[1]).distance(Point(coords[2]))

        if d1 < d2:
            return [LineString([m1, m2])]
        else:
            m3 = LineString([coords[1], coords[2]]).interpolate(0.5, normalized=True)
            m4 = LineString([coords[3], coords[0]]).interpolate(0.5, normalized=True)
            return [LineString([m3, m4])]

# implement strategy for X corridor

class XCorridorStrategy(CenterLineStrategy):
    """Handles 4-way intersections (12 points)"""

    def draw(self, polygon: Polygon) -> list[LineString]:
        coords = list(polygon.exterior.coords)[:-1]
        center = polygon.centroid

        # Identify end-cap midpoints (assuming regular 12-point cross)
        # Points 1-2, 4-5, 7-8, 10-11 in 1-based
        caps = [(0, 1), (3, 4), (6, 7), (9, 10)]
        lines = []
        for pair in caps:
            mid = LineString([coords[pair[0]], coords[pair[1]]]).interpolate(0.5, normalized=True)
            lines.append(LineString([mid, center]))
        return lines

# update the GEOJSON of floor 3


# =========================
# CONTEXT / COORDINATOR
# =========================
class CenterLineDrawer:
    def __init__(self):
        self._strategies = {
            "I": ICorridorStrategy(),
            "L": LCorridorStrategy(),
            "T": TCorridorStrategy(),
            "X": XCorridorStrategy()
        }

    def get_strategy(self, polygon: Polygon):
        num_points = len(polygon.exterior.coords) - 1
        if num_points <= 5: return self._strategies["I"]
        if num_points == 6: return self._strategies["L"]
        if num_points >= 8 and num_points <= 10: return self._strategies["T"]
        if num_points >= 11: return self._strategies["X"]
        return self._strategies["I"]

    def process_geojson(self, data):
        new_features = []
        for feature in data["features"]:
            geom = shape(feature["geometry"])
            # Only process corridor Polygons
            if feature["properties"].get("space_type") == "corridor" and geom.geom_type == "Polygon":
                strategy = self.get_strategy(geom)
                lines = strategy.draw(geom)

                for i, line in enumerate(lines):
                    new_feat = feature.copy()
                    new_feat["geometry"] = mapping(line)
                    # Preserve original metadata but tag as center line
                    new_feat["properties"]["geometry_type"] = "centerline"
                    new_feat["properties"]["uid"] = f"{feature['properties'].get('uid', 'corr')}_L{i}"
                    new_features.append(new_feat)
            else:
                new_features.append(feature)

        data["features"] = new_features
        return data


# =========================
# EXECUTION
# =========================
def main():
    # Load your file
    input_filename = "floor3_utm.geojson"
    output_filename = "floor3_centerlines.geojson"

    try:
        with open(input_filename, "r") as f:
            geojson_data = json.load(f)

        drawer = CenterLineDrawer()
        updated_data = drawer.process_geojson(geojson_data)

        with open(output_filename, "w") as f:
            json.dump(updated_data, f, indent=2)

        print(f"Success! Center lines generated in {output_filename}")

    except FileNotFoundError:
        print(f"Error: {input_filename} not found.")


if __name__ == "__main__":
    main()