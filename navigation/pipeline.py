from .create_path import get_google_route
from .decode_route import extract_route_points
from .navigate import navigate
from .movement import movement
from .self_navigation.shortest_distance import short_distance

routing_engine = "google" # Default routing engine

def set_routing_engine(engine: str):
    global routing_engine
    routing_engine = engine

def fetch_routes(kart_coords, marketplace_coords, delivery_coords):
    """Fetch routes based on the selected routing engine. Call this once, not every frame."""
    global routing_engine
    
    if routing_engine == "self":
        kc = {'lats': kart_coords.latitude, 'longs': kart_coords.longitude}
        mc = {'lats': marketplace_coords.latitude, 'longs': marketplace_coords.longitude}
        dc = {'lats': delivery_coords.latitude, 'longs': delivery_coords.longitude}
        
        receive_points = short_distance(kc, mc)
        deliver_points = short_distance(kc, dc)
        return {
            "receive_points": receive_points,
            "deliver_points": deliver_points
        }
    else:
        receive_path = get_google_route(kart_coords, marketplace_coords)
        deliver_path = get_google_route(kart_coords, delivery_coords)
        receive_points = extract_route_points(receive_path)
        deliver_points = extract_route_points(deliver_path)
        return {
            "receive_points": receive_points,
            "deliver_points": deliver_points
        }


def run_navigation_step(heading, kart_coords, route_points, frame):
    """Run a single navigation step: check obstacles then steer."""
    # Safety first: check for obstacles in the camera frame
    obstacle_check = movement(frame)
    if obstacle_check == "STOP":
        return {"command": "STOP", "reason": "obstacle_detected"}
    
    # Path is clear, calculate steering command
    nav_result = navigate(heading, kart_coords, route_points)
    return {"command": nav_result.get("command", "STOP"), "reason": "navigation"}
