import math

def calculate_distance(point1, point2):
    lat1, lon1 = point1
    lat2, lon2 = point2
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    EARTH_RADIUS = 6371000
    return EARTH_RADIUS * c


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

WAYPOINT_REACHED_RADIUS = 8.0   # meters — when we're this close, advance to the next waypoint
WAYPOINT_LOOKAHEAD = 2          # skip ahead this many points for smoother curves

def get_next_waypoint(current_coords, points, current_index):
    """
    Given the cart's current GPS position, the full route, and the current
    waypoint index, determine the target waypoint to steer toward.
    
    Returns (target_point_tuple, updated_index).
    
    Logic:
      1. If we're within WAYPOINT_REACHED_RADIUS of the current target, advance.
      2. Keep advancing past any waypoints we've already overshot.
      3. Apply a small lookahead for smoother cornering.
      4. Never go backward.
    """
    if not points or current_index >= len(points):
        return None, current_index

    current = to_tuple(current_coords)
    idx = current_index

    # Advance past any waypoints we've already reached or overshot
    while idx < len(points):
        wp = to_tuple(points[idx])
        dist = calculate_distance(current, wp)
        if dist < WAYPOINT_REACHED_RADIUS:
            idx += 1  # We reached this one, move to the next
        else:
            break  # This waypoint is still ahead of us

    # Apply lookahead for smoother steering (aim a bit further ahead on curves)
    target_idx = min(idx + WAYPOINT_LOOKAHEAD, len(points) - 1)

    # If we've passed ALL waypoints, we've reached the end
    if idx >= len(points):
        return None, idx

    target = to_tuple(points[target_idx])
    return target, idx