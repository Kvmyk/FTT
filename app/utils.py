import json
import os
from geopy.geocoders import Nominatim
from functools import lru_cache
import math
import requests
import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

geolocator = Nominatim(user_agent=os.environ.get('USER_AGENT'))


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
    url = os.environ.get('OSRM_URL')
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None
    
def is_hate_speech(text):
    url = os.environ.get('MOP_URL')
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "text": text
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Sprawdź, czy odpowiedź jest poprawna
        result = response.json()
        logging.info(f"Response from hate speech analysis: {result}")
        return result.get('label') == 'hate'
    except requests.RequestException as e:
        logging.error(f"Błąd podczas analizy mowy nienawiści: {e}")
        return False  # Domyślnie zwracamy False w przypadku błędu
    
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

def format_distance_text(distance):
    if distance < 1000:
        return f"{int(distance)} m"
    else:
        return f"{distance/1000:.2f} km"
    
def isInOpoleProvince(lat, lon):
        """
        Sprawdza, czy podane współrzędne znajdują się w granicach województwa opolskiego.
        """
        # Granice województwa opolskiego (przybliżone)
        opole_bounds = {
            'north': 51.0,
            'south': 49.5,
            'west': 16.5,
            'east': 18.5
        }

        return opole_bounds['south'] <= lat <= opole_bounds['north'] and \
            opole_bounds['west'] <= lon <= opole_bounds['east']