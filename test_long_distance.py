import os
import sys
from dotenv import load_dotenv

# Dodaj folder app do path żeby móc importować utils
sys.path.append('app')

load_dotenv()

from utils import get_route_openrouteservice, get_route_osrm_fallback

def test_long_distance_route():
    """Test routing between Opole and Wrocław"""
    
    # Opole coordinates (approximate city center)
    opole_lat = 50.6751
    opole_lon = 17.9213
    
    # Wrocław coordinates (approximate city center)
    wroclaw_lat = 51.1079
    wroclaw_lon = 17.0385
    
    print(f"Testing route from Opole ({opole_lat}, {opole_lon}) to Wrocław ({wroclaw_lat}, {wroclaw_lon})")
    print("Distance: approximately 90km")
    print()
    
    # Test OpenRouteService
    print("1. Testing OpenRouteService...")
    try:
        result = get_route_openrouteservice(opole_lat, opole_lon, wroclaw_lat, wroclaw_lon)
        if result:
            route = result['routes'][0]
            distance_km = route['distance'] / 1000
            duration_hours = route['duration'] / 3600
            print(f"✅ OpenRouteService SUCCESS!")
            print(f"   Distance: {distance_km:.1f} km")
            print(f"   Duration: {duration_hours:.1f} hours")
            print(f"   Coordinates count: {len(route['geometry']['coordinates'])}")
        else:
            print("❌ OpenRouteService FAILED - No route returned")
    except Exception as e:
        print(f"❌ OpenRouteService ERROR: {e}")
    
    print()
    
    # Test OSRM fallback
    print("2. Testing OSRM fallback...")
    try:
        result = get_route_osrm_fallback(opole_lat, opole_lon, wroclaw_lat, wroclaw_lon)
        if result and 'routes' in result and len(result['routes']) > 0:
            route = result['routes'][0]
            distance_km = route['distance'] / 1000
            duration_hours = route['duration'] / 3600
            print(f"✅ OSRM fallback SUCCESS!")
            print(f"   Distance: {distance_km:.1f} km")
            print(f"   Duration: {duration_hours:.1f} hours")
            print(f"   Coordinates count: {len(route['geometry']['coordinates'])}")
        else:
            print("❌ OSRM fallback FAILED - No route returned")
    except Exception as e:
        print(f"❌ OSRM fallback ERROR: {e}")

if __name__ == "__main__":
    test_long_distance_route()
