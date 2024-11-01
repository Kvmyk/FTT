import json
from geopy.geocoders import Nominatim
from functools import lru_cache

geolocator = Nominatim(user_agent="test")

@lru_cache(maxsize=100)
def get_coordinates(location):
    location = geolocator.geocode(location)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None