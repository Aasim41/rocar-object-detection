import os
import requests
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("GMAPS_API_KEY", "AIzaSyBX0xNBFK24V2DZgMQHFku3tWcJWtVjgds")
URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
def coordinates_to_location(coordinates):
    return {
        "location": {
            "latLng": {
                "latitude": coordinates.latitude,
                "longitude": coordinates.longitude
            }
        }
    }
def get_google_route(origin, destination):
    data = {
        "origin": coordinates_to_location(origin),
        "destination": coordinates_to_location(destination),
        "travelMode": "DRIVE"
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": (
            "routes.distanceMeters,"
            "routes.duration,"
            "routes.legs.steps.distanceMeters,"
            "routes.legs.steps.startLocation,"
            "routes.legs.steps.endLocation,"
            "routes.steps.polyline"
        )
    }
    response = requests.post(
        URL,
        headers=headers,
        json=data
    )
    print("Google Status:", response.status_code)
    if response.status_code != 200:
        print("Google Error:")
        print(response.text)
        return None
    return response.json()