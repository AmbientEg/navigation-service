from pathlib import Path

import networkx as nx

from construct_graph import (
    add_junctions,
    attach_doors,
    attach_rooms,
    classify_features,
    check_connectivity,
    export_graph,
    load_geojson,
    build_corridor_backbone,
    visualize_graph,
)


def build_navigation_graph(input_geojson: str) -> nx.Graph:
    """Build and return the navigation graph from a floor GeoJSON file."""
    data = load_geojson(input_geojson)
    corridor_lines, doors, rooms, _ = classify_features(data)

    graph = nx.Graph()
    build_corridor_backbone(graph, corridor_lines)
    add_junctions(graph)
    attach_doors(graph, doors, corridor_lines)
    attach_rooms(graph, rooms)
    return graph


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_geojson = base_dir / "floor3_updated.geojson"
    output_geojson = base_dir / "navigation_graph_export.geojson"

    if not input_geojson.exists():
        raise FileNotFoundError(f"Input file not found: {input_geojson}")

    graph = build_navigation_graph(str(input_geojson))

    check_connectivity(graph)
    export_graph(graph, str(output_geojson))
    print(f"Exported graph to: {output_geojson}")

    # Visualize graph
    visualize_graph(graph)


if __name__ == "__main__":
    main()
