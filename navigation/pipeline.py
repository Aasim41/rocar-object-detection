from .create_path import get_google_route
from .decode_route import extract_route_points
from .self_navigation.shortest_distance import short_distance
from .self_navigation.close_coords import check_self_dependence

routing_engine = "google"
route_cache = {}

def set_routing_engine(engine: str):
    global routing_engine
    routing_engine = engine

def simplify_route(points, min_distance_meters=2.0):
    """
    Filter route points so that no two consecutive points are closer than min_distance_meters.
    This prevents micro-waypoints from causing jerky steering.
    """
    if not points or len(points) <= 2:
        return points
        
    from .fnpp import calculate_distance, to_tuple
    simplified = [points[0]]
    last_added = to_tuple(points[0])
    
    for i in range(1, len(points) - 1):
        pt = to_tuple(points[i])
        if calculate_distance(last_added, pt) >= min_distance_meters:
            simplified.append(points[i])
            last_added = pt
            
    # Always keep the final destination
    simplified.append(points[-1])
    return simplified

def _campus_coord_dict(coords):
    return {"lats": coords.latitude, "longs": coords.longitude}

def _fallback_to_campus_graph(kart_coords, marketplace_coords, delivery_coords, receive_points, deliver_points):
    """Fallback to JUET internal graph if Google Maps returns no route points."""
    kc = _campus_coord_dict(kart_coords)
    mc = _campus_coord_dict(marketplace_coords)
    dc = _campus_coord_dict(delivery_coords)
    if not check_self_dependence(kc, mc):
        return receive_points, deliver_points
    if not receive_points:
        receive_points = short_distance(kc, mc)
    if not deliver_points:
        deliver_points = short_distance(mc, dc)
    return receive_points, deliver_points

def fetch_routes(kart_coords, marketplace_coords, delivery_coords):
    """
    Fetch pickup and delivery routes using selected engine (Google Maps or internal campus graph).
    Call this once when an order is created. Includes caching and point simplification.
    """
    global routing_engine, route_cache
    
    # Helper to format cache keys consistently (rounded to ~11m precision to group identical stops)
    def cache_key(src, dst):
        s_lat, s_lng = round(src.latitude, 4), round(src.longitude, 4)
        d_lat, d_lng = round(dst.latitude, 4), round(dst.longitude, 4)
        return f"{routing_engine}:{s_lat},{s_lng}->{d_lat},{d_lng}"

    k_key = cache_key(kart_coords, marketplace_coords)
    m_key = cache_key(marketplace_coords, delivery_coords)
    
    receive_points = route_cache.get(k_key)
    deliver_points = route_cache.get(m_key)
    
    if routing_engine == "self":
        kc = _campus_coord_dict(kart_coords)
        mc = _campus_coord_dict(marketplace_coords)
        dc = _campus_coord_dict(delivery_coords)
        
        if not receive_points:
            receive_points = short_distance(kc, mc)
            route_cache[k_key] = receive_points
            
        if not deliver_points:
            deliver_points = short_distance(mc, dc)
            route_cache[m_key] = deliver_points
            
    else:
        if not receive_points:
            receive_path = get_google_route(kart_coords, marketplace_coords)
            receive_points = extract_route_points(receive_path)
            
        if not deliver_points:
            deliver_path = get_google_route(marketplace_coords, delivery_coords)
            deliver_points = extract_route_points(deliver_path)
            
        receive_points, deliver_points = _fallback_to_campus_graph(
            kart_coords, marketplace_coords, delivery_coords, receive_points, deliver_points
        )
        
        route_cache[k_key] = receive_points
        route_cache[m_key] = deliver_points

    return {
        "receive_points": simplify_route(receive_points, min_distance_meters=2.0),
        "deliver_points": simplify_route(deliver_points, min_distance_meters=2.0)
    }
