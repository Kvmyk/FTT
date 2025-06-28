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
    """Get walking route using OpenRouteService API (free alternative to OSRM)"""
    api_key = os.environ.get('OPENROUTESERVICE_API_KEY')
    
    if not api_key:
        logging.error("OPENROUTESERVICE_API_KEY not found in environment variables")
        return None
    
    url = "https://api.openrouteservice.org/v2/directions/foot-walking"
    
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    
    data = {
        "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
        "format": "geojson",
        "instructions": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            # Convert to OSRM-like format for compatibility
            if 'features' in result and len(result['features']) > 0:
                feature = result['features'][0]
                return {
                    "routes": [{
                        "geometry": feature['geometry'],
                        "distance": feature['properties']['summary']['distance'],
                        "duration": feature['properties']['summary']['duration']
                    }]
                }
            return None
        else:
            logging.error(f"OpenRouteService API error: {response.status_code}")
            return None
    except requests.RequestException as e:
        logging.error(f"Error connecting to OpenRouteService API: {e}")
        return None
    
def is_hate_speech(text):
    """Check if text contains hate speech using Google Gemini API"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        logging.error("GEMINI_API_KEY not found in environment variables")
        return False
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    
    prompt = f"""
Sprawdź poniższą treść pod kątem mowy nienawiści, obraźliwych słów, wulgarizmów, dyskryminacji, przemocy lub innych nieodpowiednich treści. 

Treść do sprawdzenia: "{text}"

Odpowiedz tylko jednym słowem:
- "OK" - jeśli treść jest odpowiednia i nie zawiera mowy nienawiści
- "NOT OK" - jeśli treść zawiera mowę nienawiści, wulgaryzmy lub jest nieodpowiednia

Odpowiedź:"""

    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        # Extract the response text
        if 'candidates' in result and len(result['candidates']) > 0:
            response_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            logging.info(f"Gemini response for text '{text[:50]}...': {response_text}")
            
            # Return True if NOT OK (contains hate speech)
            return "NOT OK" in response_text.upper()
        else:
            logging.error(f"Unexpected Gemini API response format: {result}")
            return False
            
    except requests.RequestException as e:
        logging.error(f"Error connecting to Gemini API: {e}")
        return False  # Default to allowing content if API fails
    except Exception as e:
        logging.error(f"Error processing Gemini API response: {e}")
        return False
    
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