import math
from .fnpp import get_next_waypoint, to_tuple

def calculate_bearing(point1, point2):
    lat1, lon1 = to_tuple(point1)
    lat2, lon2 = to_tuple(point2)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    y = math.sin(delta_lon) * math.cos(lat2)
    x = (
        math.cos(lat1) * math.sin(lat2)
        -
        math.sin(lat1)
        * math.cos(lat2)
        * math.cos(delta_lon)
    )
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360
    return bearing

def angle_difference(desired_bearing, current_bearing):
    difference = desired_bearing - current_bearing
    difference = (difference + 180) % 360 - 180
    return difference

def generate_command(angle_error):
    if abs(angle_error) <= 10:
        return "F"
    elif 10 < angle_error <= 30:
        return "SR"
    elif -30 <= angle_error < -10:
        return "SL"
    elif angle_error > 30:
        return "R"
    else:
        return "L"

def navigate(heading, current_coords, points, waypoint_index=0):
    """
    Navigate the cart along a route using progressive waypoint tracking.
    
    Args:
        heading: Current compass heading (degrees from north)
        current_coords: Current GPS position (dict or tuple)
        points: Full list of route waypoints
        waypoint_index: Current waypoint index (tracks progress through route)
    
    Returns:
        dict with "command" (F/L/R/SL/SR) and "waypoint_index" (updated index)
    """
    if not points:
        return {"command": "F", "waypoint_index": waypoint_index}

    # Use the progressive tracker instead of the old closest-point finder
    next_point, new_index = get_next_waypoint(current_coords, points, waypoint_index)
    
    if next_point is None:
        # We've passed all waypoints — route complete
        return {"command": "F", "waypoint_index": new_index, "route_complete": True}

    desired_bearing = calculate_bearing(current_coords, next_point)
    angle_error = angle_difference(desired_bearing, heading)
    command = generate_command(angle_error)

    return {
        "command": command,
        "waypoint_index": new_index
    }