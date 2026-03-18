import geopandas as gpd

INPUT = "floor3.geojson"
OUTPUT = "floor3_utm.geojson"

def main():
    gdf = gpd.read_file(INPUT)

    # Convert WGS84 → UTM Zone 36N (Cairo)
    gdf = gdf.to_crs(epsg=32636)

    gdf.to_file(OUTPUT, driver="GeoJSON")

    print("Reprojected to UTM:", OUTPUT)

if __name__ == "__main__":
    main()