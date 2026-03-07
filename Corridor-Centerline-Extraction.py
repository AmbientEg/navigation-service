import json
import numpy as np
from shapely.geometry import shape, LineString
from shapely.validation import make_valid

# =========================
# LOAD GEOJSON
# =========================
with open("floor3.geojson") as f:
    data = json.load(f)

# =========================
# FIND CORRIDOR
# =========================
feature = next(
    f for f in data["features"]
    if f["properties"].get("space_type") == "corridor"
)

poly = shape(feature["geometry"])
poly = make_valid(poly)

# =========================
# EXTRACT EXTERIOR COORDS
# =========================
coords = np.array(poly.exterior.coords)

# Remove duplicate last point
coords = coords[:-1]

# =========================
# COMPUTE CENTROID
# =========================
centroid = coords.mean(axis=0)

# =========================
# PCA (Principal Direction)
# =========================
cov = np.cov(coords.T)
eigenvalues, eigenvectors = np.linalg.eig(cov)

# Take eigenvector with largest eigenvalue
principal_axis = eigenvectors[:, np.argmax(eigenvalues)]

# Normalize
principal_axis = principal_axis / np.linalg.norm(principal_axis)

# =========================
# PROJECT POINTS ONTO AXIS
# =========================
projections = np.dot(coords - centroid, principal_axis)

min_proj = projections.min()
max_proj = projections.max()

start = centroid + min_proj * principal_axis
end = centroid + max_proj * principal_axis

centerline = LineString([tuple(start), tuple(end)])

# =========================
# EXPORT
# =========================
output = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "fid": 1,
                "space_type": "corridor",
                "floor": 3,
                "routing_cost": 1
            },
            "geometry": {
                "type": "LineString",
                "coordinates": list(centerline.coords)
            }
        }
    ]
}

with open("corridor_centerline.geojson", "w") as f:
    json.dump(output, f, indent=2)

print("Centerline exported.")