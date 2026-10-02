import math

def calculate_distance(point1, point2):
    """Calculate great-circle distance in meters between two (lat, lng) points."""
    lat1, lon1 = point1
    lat2, lon2 = point2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(phi1) * math.cos(phi2)
        * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371000 * c


def to_tuple(coords):
    """Convert coords to (lat, lng) tuple. Accepts tuple, list, dict, or Pydantic model."""
    if coords is None:
        return (0.0, 0.0)
    if isinstance(coords, (tuple, list)):
        return (coords[0], coords[1])
    if isinstance(coords, dict):
        lat = coords.get("latitude", coords.get("lat"))
        lng = coords.get("longitude", coords.get("lng"))
        return (lat, lng)
    try:
        return (coords.latitude, coords.longitude)
    except AttributeError:
        return (0.0, 0.0)


def polypoint(current_coords, points):
    """Legacy closest-point finder. Kept for backward compatibility."""
    if not points:
        return None
    current = to_tuple(current_coords)
    closest_point = None
    shortest_distance = float("inf")
    for point in points:
        route_point = to_tuple(point)
        distance = calculate_distance(current, route_point)
        if distance < shortest_distance:
            shortest_distance = distance
            closest_point = route_point
    return closest_point


# ============================================================
# Progressive Waypoint Tracker (replaces polypoint for routing)
# ============================================================
# Instead of always finding the closest point (which can go backward),
# this advances through the route waypoints sequentially.

WAYPOINT_REACHED_RADIUS = 5.0    # meters — tightened up slightly since we simplified the route
WAYPOINT_LOOKAHEAD_DIST = 4.0    # physical meters to look ahead for smooth steering

def get_next_waypoint(current_coords, points, current_index):
    """
    Given the cart's current GPS position, the full route, and the current
    waypoint index, determine the target waypoint to steer toward using Pure Pursuit logic.
    
    Returns (target_point_tuple, updated_index).
    """
    if not points or current_index >= len(points):
        return None, current_index

    current = to_tuple(current_coords)
    idx = current_index

    # 1. Advance past any waypoints we've already reached
    while idx < len(points) - 1:
        wp = to_tuple(points[idx])
        dist = calculate_distance(current, wp)
        if dist < WAYPOINT_REACHED_RADIUS:
            idx += 1
        else:
            break

    # If we reached the final waypoint
    if idx >= len(points) - 1:
        dist_to_final = calculate_distance(current, to_tuple(points[-1]))
        if dist_to_final < WAYPOINT_REACHED_RADIUS:
            return None, len(points)
        return to_tuple(points[-1]), idx

    # 2. Pure Pursuit Lookahead: find a point further along the path that is at least
    # WAYPOINT_LOOKAHEAD_DIST meters away from the *current* waypoint.
    target_idx = idx
    current_wp = to_tuple(points[idx])
    
    while target_idx < len(points) - 1:
        lookahead_wp = to_tuple(points[target_idx])
        if calculate_distance(current_wp, lookahead_wp) >= WAYPOINT_LOOKAHEAD_DIST:
            break
        target_idx += 1

    target = to_tuple(points[target_idx])
    return target, idx