# routes_store.py
import json
import os
import time

class RoutesStore:
    def __init__(self):
        self.routes_file = os.path.join('data', 'routes.json')
        self.routes = self.load_routes()
        self.routes_cache = {}
        self.cache_timeout = 3600  # 1 godzina
    
    def load_routes(self):
        try:
            with open(self.routes_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
            
    def save_routes(self):
        try:
            with open(self.routes_file, 'w') as f:
                json.dump(self.routes, f, indent=4)
        except Exception as e:
            print(f"Error saving routes: {e}")

    def cleanup_old_routes(self):
        current_time = time.time()
        self.routes = {k:v for k,v in self.routes.items() 
                       if v.get('timestamp', 0) > current_time - 86400}  # 24h