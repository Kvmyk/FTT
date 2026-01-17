import json
import os
from geopy.geocoders import Nominatim
from functools import lru_cache
import math
import requests
import logging
import google.generativeai as genai

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
    # Use standard OSRM demo server - simpler and often more reliable for demos
    # Note: foot profile on demo server might route on streets, but it works
    url = f"https://router.project-osrm.org/route/v1/foot/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    
    logging.info(f"Fetching route from: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        logging.info(f"OSRM response code: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        
        logging.error(f"OSRM Error: {response.status_code}")
        return None
            
    except requests.RequestException as e:
        logging.error(f"OSRM service exception: {e}")
        return None
    
def is_hate_speech(text):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logging.warning("GEMINI_API_KEY not set. Skipping hate speech check.")
        return False

    if not text or len(text.strip()) == 0:
        return False

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Jesteś moderatorem treści. Przeanalizuj poniższy tekst pod kątem mowy nienawiści, wulgaryzmów, treści obraźliwych, rasistowskich lub seksualnych.
        
        Tekst: "{text}"
        
        Jeśli tekst zawiera niedozwolone treści, odpowiedz tylko słowem "TAK".
        Jeśli tekst jest bezpieczny, odpowiedz tylko słowem "NIE".
        """
        
        response = model.generate_content(prompt)
        answer = response.text.strip().upper()
        
        logging.info(f"Gemini analysis for '{text}': {answer}")
        
        return "TAK" in answer
    except Exception as e:
        logging.error(f"Error checking hate speech with Gemini: {e}")
        return False # Fail open (allow text) if API fails to avoid blocking users
    
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
