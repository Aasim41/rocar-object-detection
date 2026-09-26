import math
from .polyline import polypoints_db

def calculate_distance(point1, point2):
    """Haversine distance in meters between two (lat, lon) points."""
    lat1, lon1 = point1
    lat2, lon2 = point2
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371000 * c

def close_coords(current_coords):
    """Find the closest graph vertex to the given coordinates."""
    current_point = (current_coords["lats"], current_coords["longs"])
    closest_vertex = None
    shortest_distance = float("inf")
    for vertex, coordinates in polypoints_db.items():
        vertex_point = (coordinates["lats"], coordinates["longs"])
        distance = calculate_distance(current_point, vertex_point)
        if distance < shortest_distance:
            shortest_distance = distance
            closest_vertex = vertex
    return closest_vertex

def check_self_dependence(kart_coords, marketplace_coords):
    """Check if kart and marketplace are within campus boundaries (<= 1000m)."""
    p1 = (kart_coords["lats"], kart_coords["longs"])
    p2 = (marketplace_coords["lats"], marketplace_coords["longs"])
    return 1 if calculate_distance(p1, p2) <= 1000.0 else 0