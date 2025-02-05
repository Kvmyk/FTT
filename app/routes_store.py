# routes_store.py
import json
import os
import time

class RoutesStore:
    def __init__(self):
        self.routes_file = os.path.join('data', 'routes.json')
        self.routes = self.load_routes()
        self.cache_timeout = 3600  # 1 godzina
        self.last_cleanup = time.time()
        self.cleanup_interval = 86400  # 24 godziny
    
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
        """Czyści stare trasy z cache"""
        current_time = time.time()
        
        # Wykonuj czyszczenie tylko raz na 24h
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        # Usuń trasy starsze niż cache_timeout
        self.routes = {
            route_id: route_data 
            for route_id, route_data in self.routes.items()
            if current_time - route_data.get('timestamp', 0) < self.cache_timeout
        }
        
        # Zapisz wyczyszczone trasy
        self.save_routes()
        self.last_cleanup = current_time

    def add_route(self, route_id, route_data):
        """Dodaj nową trasę z timestamp"""
        self.routes[route_id] = {
            'data': route_data,
            'timestamp': time.time()
        }
        self.save_routes()