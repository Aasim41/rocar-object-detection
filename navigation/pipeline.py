from .create_path import get_google_route
from .decode_route import extract_route_points
from .self_navigation.shortest_distance import short_distance
from .self_navigation.close_coords import check_self_dependence

routing_engine = "google"

def set_routing_engine(engine: str):
    global routing_engine
    routing_engine = engine

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
    Call this once when an order is created.
    """
    global routing_engine
    
    if routing_engine == "self":
        kc = _campus_coord_dict(kart_coords)
        mc = _campus_coord_dict(marketplace_coords)
        dc = _campus_coord_dict(delivery_coords)
        
        receive_points = short_distance(kc, mc)
        deliver_points = short_distance(mc, dc)
        return {
            "receive_points": receive_points,
            "deliver_points": deliver_points
        }
    else:
        receive_path = get_google_route(kart_coords, marketplace_coords)
        deliver_path = get_google_route(marketplace_coords, delivery_coords)
        receive_points = extract_route_points(receive_path)
        deliver_points = extract_route_points(deliver_path)
        receive_points, deliver_points = _fallback_to_campus_graph(
            kart_coords, marketplace_coords, delivery_coords, receive_points, deliver_points
        )
        return {
            "receive_points": receive_points,
            "deliver_points": deliver_points
        }
