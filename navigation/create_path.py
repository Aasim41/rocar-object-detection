import os
import requests
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("GMAPS_API_KEY", "AIzaSyBX0xNBFK24V2DZgMQHFku3tWcJWtVjgds")
URL = "https://maps.googleapis.com/maps/api/directions/json"

def get_google_route(origin, destination):
    params = {
        "origin": f"{origin.latitude},{origin.longitude}",
        "destination": f"{destination.latitude},{destination.longitude}",
        "mode": "walking",
        "key": API_KEY
    }
    try:
        response = requests.get(URL, params=params, timeout=10)
        if response.status_code != 200:
            print("Google Directions Error:", response.text)
            return None
        data = response.json()
        if data.get("status") != "OK":
            print("Google Directions Status Error:", data.get("status"), data.get("error_message"))
            return None
        return data
    except Exception as e:
        print("Google Directions Exception:", str(e))
        return None