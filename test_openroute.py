#!/usr/bin/env python3
# Test script for OpenRouteService API

import sys
import os
sys.path.append('app')

from dotenv import load_dotenv
load_dotenv()

from utils import get_route

def test_openrouteservice():
    print("Testing OpenRouteService API...")
    
    # Test coordinates (somewhere in Poland)
    start_lat, start_lon = 50.0647, 19.9450  # Kraków
    end_lat, end_lon = 50.0657, 19.9460      # Nearby point
    
    print(f"Getting route from ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")
    
    result = get_route(start_lat, start_lon, end_lat, end_lon)
    
    if result:
        print("✅ Route found!")
        if 'routes' in result and len(result['routes']) > 0:
            route = result['routes'][0]
            distance = route.get('distance', 0)
            duration = route.get('duration', 0)
            print(f"Distance: {distance} meters")
            print(f"Duration: {duration} seconds")
            print(f"Coordinates count: {len(route['geometry']['coordinates'])}")
        else:
            print("❌ No routes in response")
    else:
        print("❌ No route found")

if __name__ == "__main__":
    test_openrouteservice()
