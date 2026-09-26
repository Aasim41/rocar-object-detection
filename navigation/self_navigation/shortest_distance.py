from .distance_graph import juet_weighted_graph
from .close_coords import close_coords as cc
from .result_convertor import result_convertor

def extract_vertices(current_vertex, end_vertex, path, distance, result):
    """DFS path search across weighted campus graph."""
    if current_vertex == end_vertex:
        result[tuple(path)] = distance
        return

    node_data = juet_weighted_graph.get(current_vertex)
    if not node_data:
        return

    connections = node_data.get("connections", {})
    for next_vertex, edge_distance in connections.items():
        if next_vertex not in juet_weighted_graph or next_vertex in path:
            continue
        extract_vertices(
            next_vertex,
            end_vertex,
            path + [next_vertex],
            distance + edge_distance,
            result
        )

def short_distance(kart_coords, target_coords):
    """Find shortest path between kart position and target position on campus graph."""
    start_vertex = cc(kart_coords)
    end_vertex = cc(target_coords)
    result = {}
    extract_vertices(
        start_vertex,
        end_vertex,
        [start_vertex],
        0,
        result
    )

    if not result:
        return []

    shortest_path = min(result, key=result.get)
    return result_convertor(shortest_path)