import json
from geopy.geocoders import Nominatim
from functools import lru_cache
import math
import requests
#test
geolocator = Nominatim(user_agent="test")

@lru_cache(maxsize=100)
def get_coordinates(location):
    location = geolocator.geocode(location)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Promień Ziemi w kilometrach
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c  # Odległość w kilometrach

def get_route(start_lat, start_lon, end_lat, end_lon):
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def find_nearest_marker(user_location, markers):
    min_distance = float('inf')
    nearest_marker = None
    for marker in markers:
        if marker['name'] != "User Location":
            distance = haversine(user_location['lat'], user_location['lon'], marker['lat'], marker['lon'])
            if distance < min_distance:
                min_distance = distance
                nearest_marker = marker
    return nearest_marker