import math

def calculate_haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lng pairs."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371000 * c

def decode_polyline(encoded):
    """Standard Google Encoded Polyline Algorithm Format decoder."""
    points = []
    index = 0
    latitude = 0
    longitude = 0
    length = len(encoded)
    while index < length:
        # Decode latitude
        result = 0
        shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if (result & 1) else (result >> 1)
        latitude += delta_lat
        
        # Decode longitude
        result = 0
        shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lng = ~(result >> 1) if (result & 1) else (result >> 1)
        longitude += delta_lng

        points.append({
            "point": len(points) + 1,
            "latitude": latitude / 100000.0,
            "longitude": longitude / 100000.0
        })
    return points

def dense_interpolate_points(points, max_step_meters=2.5):
    """
    Interpolate points so that distance between any two consecutive points
    does not exceed max_step_meters (~2.5m).
    This ensures pinpoint precision along roads, curves, and turns.
    """
    if not points or len(points) < 2:
        return points

    dense = [points[0]]
    for i in range(1, len(points)):
        p1 = dense[-1]
        p2 = points[i]
        
        lat1, lng1 = p1["latitude"], p1["longitude"]
        lat2, lng2 = p2["latitude"], p2["longitude"]
        dist = calculate_haversine(lat1, lng1, lat2, lng2)
        
        if dist > max_step_meters:
            num_subdivisions = int(math.ceil(dist / max_step_meters))
            for step in range(1, num_subdivisions):
                frac = step / float(num_subdivisions)
                interp_lat = lat1 + (lat2 - lat1) * frac
                interp_lng = lng1 + (lng2 - lng1) * frac
                dense.append({
                    "point": len(dense) + 1,
                    "latitude": round(interp_lat, 7),
                    "longitude": round(interp_lng, 7)
                })
        dense.append({
            "point": len(dense) + 1,
            "latitude": round(lat2, 7),
            "longitude": round(lng2, 7)
        })

    # Renumber sequentially
    for idx, pt in enumerate(dense):
        pt["point"] = idx + 1
    return dense

def extract_route_points(route_response, dense_interpolation=True, max_step_meters=2.5):
    """
    Extract pinpoint precision route points from Google Directions API response.
    Prioritizes step-by-step detailed polylines from legs[0].steps over coarse overview_polyline.
    Interpolates dense waypoints at ~2.5m intervals for flawless autonomous tracking.
    """
    if route_response is None:
        return []
    routes = route_response.get("routes", [])
    if not routes:
        return []
    route = routes[0]

    raw_points = []
    
    # 1. High-precision extraction: iterate over all steps in legs
    legs = route.get("legs", [])
    if legs:
        for leg in legs:
            steps = leg.get("steps", [])
            for step in steps:
                poly = step.get("polyline")
                if poly and isinstance(poly, dict) and poly.get("points"):
                    step_pts = decode_polyline(poly["points"])
                    for pt in step_pts:
                        if not raw_points or (
                            abs(raw_points[-1]["latitude"] - pt["latitude"]) > 1e-6 or
                            abs(raw_points[-1]["longitude"] - pt["longitude"]) > 1e-6
                        ):
                            raw_points.append(pt)

    # 2. Fallback to overview_polyline if legs/steps were not detailed
    if not raw_points:
        overview = route.get("overview_polyline")
        if overview and isinstance(overview, dict) and overview.get("points"):
            raw_points = decode_polyline(overview["points"])

    # 3. Routes API (v2) fallback
    if not raw_points:
        polyline = route.get("polyline")
        if polyline and isinstance(polyline, dict):
            encoded = polyline.get("encodedPolyline")
            if encoded:
                raw_points = decode_polyline(encoded)

    if not raw_points:
        return []

    # 4. Dense interpolation for pinpoint path accuracy
    if dense_interpolation and len(raw_points) >= 2:
        return dense_interpolate_points(raw_points, max_step_meters=max_step_meters)

    # Renumber
    for idx, pt in enumerate(raw_points):
        pt["point"] = idx + 1
    return raw_points
