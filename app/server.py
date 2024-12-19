# FILE: app/server.py

import os
import json
from flask import Flask, send_from_directory, jsonify, request
from utils import find_nearest_marker, get_route, format_distance_text, haversine

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        self.app.secret_key = os.getenv('FLASK_SECRET_KEY', 'domyslny_tajny_klucz')  # Ustaw swój tajny klucz
        self.markers = self.load_markers()
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def fullscreen():
            return send_from_directory('static/html', 'template.html')

        @self.app.route('/get_markers', methods=['GET'])
        def get_markers():
            return jsonify({'markers': self.markers})

        @self.app.route('/get_route', methods=['POST'])
        def get_route_endpoint():
            data = request.json
            user_lat = data['lat']
            user_lon = data['lon']
            nearest_marker = find_nearest_marker({'lat': user_lat, 'lon': user_lon}, self.markers)
            if not nearest_marker:
                return jsonify({'status': 'error', 'message': 'No toilets found'}), 404
            route = get_route(user_lat, user_lon, nearest_marker['lat'], nearest_marker['lon'])
            if not route:
                return jsonify({'status': 'error', 'message': 'Route not found'}), 404
            distance = route['routes'][0]['distance']  # Długość w metrach
            distance_text = format_distance_text(distance)
            return jsonify({
                'status': 'success',
                'distance': distance_text,
                'name': nearest_marker['name'],
                'route': route['routes'][0]['geometry']['coordinates']
            })

        @self.app.route('/nearest_toilet_distance', methods=['GET'])
        def nearest_toilet_distance():
            user_marker = next((marker for marker in self.markers if marker['name'] == "User Location"), None)
            if not user_marker:
                return jsonify({'status': 'error', 'message': 'User location not found'}), 404

            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if not nearest_marker:
                return jsonify({'status': 'error', 'message': 'No toilets found'}), 404

            distance = haversine(user_marker['lat'], user_marker['lon'], nearest_marker['lat'], nearest_marker['lon'])
            distance_text = format_distance_text(distance * 1000)  # Konwersja na metry

            return jsonify({'status': 'success', 'distance': distance_text, 'name': nearest_marker['name']})

        @self.app.route('/location', methods=['POST'])
        def location():
            data = request.json
            user_location = {
                "lat": data['lat'],
                "lon": data['lon'],
                "name": "User Location",
                "description": "This is your updated location"
            }
            with open(os.path.join('data', 'user_location.json'), 'w', encoding='utf-8') as f:
                json.dump(user_location, f)
            return jsonify({'status': 'success'})

    def load_markers(self):
        with open(os.path.join('data', 'data.json'), 'r', encoding='utf-8') as f:
            return json.load(f)

    def runThePage(self):
        self.app.run(host="0.0.0.0", port=21088, debug=True)
