def decode_polyline(encoded):
    points = []
    index = 0
    latitude = 0
    longitude = 0
    while index < len(encoded):
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
        if result & 1:
            delta_lat = ~(result >> 1)
        else:
            delta_lat = result >> 1
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
        if result & 1:
            delta_lng = ~(result >> 1)
        else:
            delta_lng = result >> 1
        longitude += delta_lng
        # Store point
        points.append({
            "point": len(points) + 1,
            "latitude": latitude / 100000.0,
            "longitude": longitude / 100000.0
        })
    return points
def extract_route_points(route_response):
    if route_response is None:
        return []
    routes = route_response.get("routes", [])
    if not routes:
        return []
    route = routes[0]
    polyline = route.get("polyline")
    if not polyline:
        return []
    encoded = polyline.get("encodedPolyline")
    if not encoded:
        return []
    return decode_polyline(encoded)