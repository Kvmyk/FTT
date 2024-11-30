import folium
import flask
import requests
import os
import geopy
import json
import base64
from flask import Flask, send_from_directory, jsonify, request
from utils import get_coordinates, get_route, find_nearest_marker

toilet_icon = "C:\\Users\\Kuba\\Desktop\\FTT\\toilet_icon.png"

class Server:
    def __init__(self):
        self.data = None
        self.app = Flask(__name__)
        self.lat, self.lon = 52.2297, 21.0122  # Default location (Warsaw, Poland)
        self.m = self.create_map()
        self.markers = self.load_markers()
        self.setup_routes()

    def create_map(self):
        return folium.Map(location=[self.lat, self.lon], tiles="Cartodb positron", zoom_start=15, overlay=False, min_zoom=2, max_zoom=18)

    def load_markers(self):
        try:
            with open('data/data.json', 'r', encoding='utf-8') as file:
                markers = json.load(file)
                if isinstance(markers, list):
                    return markers
                else:
                    print("Error: Loaded markers is not a list")
                    return []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading markers: {e}")
            return []

    def setup_routes(self):
        @self.app.route('/')
        def fullscreen():
            self.save_map()
            return send_from_directory('.', 'map.html')

        @self.app.route('/location', methods=['POST'])
        def location():
            data = request.json
            self.lat = data['lat']
            self.lon = data['lon']
            user_marker = next((marker for marker in self.markers if marker['name'] == "User Location"), None)

            if user_marker:
                user_marker.update({
                    "lat": self.lat,
                    "lon": self.lon,
                    "description": "This is your updated location"
                })
            else:
                user_marker = {
                    "lat": self.lat,
                    "lon": self.lon,
                    "name": "User Location",
                    "description": "This is your location",
                }
                self.markers.append(user_marker)
            with open('user_location.json', 'w', encoding='utf-8') as file:
                json.dump(user_marker, file, ensure_ascii=False, indent=4)
            self.update_map()
            self.save_map()

            # Usuwamy user_marker z self.markers przed zapisaniem innych markerów
            self.markers = [marker for marker in self.markers if marker['name'] != "User Location"]
            self.save_markers()

            # Znajdź najbliższy marker i oblicz trasę
            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if nearest_marker:
                route = get_route(self.lat, self.lon, nearest_marker['lat'], nearest_marker['lon'])
                if route:
                    self.add_route_to_map(route)
                    self.save_map()
                    self.save_markers()


            return jsonify({'status': 'success', 'lat': self.lat, 'lon': self.lon})

        @self.app.route('/submit', methods=['POST'])
        def submit():
            data = request.form
            userInput = data.get('userInput', '')
            description = data.get('description', '')
            payable = data.get('payable', 'false').lower() == 'true'
            onlyForClients = data.get('onlyForClients', 'false').lower() == 'true'
            rating = data.get('rating', '0')
            photo = request.files.get('photos')

            photo_base64 = base64.b64encode(photo.read()).decode('utf-8') if photo else None

            lat, lon = get_coordinates(userInput)
            if lat and lon:
                new_marker = {
                    "lat": lat,
                    "lon": lon,
                    "name": userInput,
                    "description": description,
                    "payable": payable,
                    "onlyForClients": onlyForClients,
                    "rating": rating,
                    "photo": photo_base64
                }
                self.markers.append(new_marker)
                self.add_marker_to_map(new_marker)  

                self.save_map()
                self.save_markers()
                return jsonify({'status': 'success', 'lat': lat, 'lon': lon})
            else:
                return jsonify({'status': 'error', 'message': 'Location not found'})

        @self.app.after_request
        def add_header(response):
            response.headers['Cache-Control'] = 'no-store'
            return response

    def add_marker_to_map(self, marker):
        if marker['name'] == "User Location":
            icon = folium.CustomIcon(toilet_icon, icon_size=(50, 50), shadow_size=(50, 50))
            popup_content = f'''
                <div style="width: 300px;">
                    <h2 style="font-size: 1.5em;">User Location</h2>
                    <p style="font-size: 1em;">{marker['description']}</p>
                </div>
            '''
            folium.Marker(location=[marker['lat'], marker['lon']], popup=popup_content, icon=icon).add_to(self.m)
        else:
            iconToilet = folium.CustomIcon(toilet_icon, icon_size=(50, 50), shadow_size=(50, 50))
            name = marker.get('name', 'Unknown')
            description = marker.get('description', 'No description')
            payable = "TAK" if marker.get('payable', True) else "NIE"
            onlyForClients = "TAK" if marker.get('onlyForClients', True) else "NIE"
            rating = marker.get('rating', 'Brak oceny')
            photo_base64 = marker.get('photo', None)
            photo_html = f'<img src="data:image/png;base64,{photo_base64}" style="width: 100%; height: auto;">' if photo_base64 else ''
            wholePopUp = f'''
                <div style="width: 300px;">
                    <h2 style="font-size: 1.5em;">{name}</h2>
                    <p style="font-size: 1em;">{description}</p>
                    <p><strong>Płatna:</strong> {payable}</p>
                    <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                    <p><strong>Ocena:</strong> {rating}</p>
                    {photo_html}
                </div>
            '''
            folium.Marker(location=[marker['lat'], marker['lon']], popup=wholePopUp, icon=iconToilet).add_to(self.m)

    def add_route_to_map(self, route):
        folium.PolyLine(
            locations=[(coord[1], coord[0]) for coord in route['routes'][0]['geometry']['coordinates']],
            color='blue',
            weight=5,
            opacity=0.7
        ).add_to(self.m)

    def update_map(self):
        self.m = self.create_map()
        for marker in self.markers:
            self.add_marker_to_map(marker)
        self.save_map()

    def save_map(self):
        self.m.save('map.html')
        with open('template.html', 'r', encoding='utf-8') as template_file:
            template_content = template_file.read()
        with open('map.html', 'a', encoding='utf-8') as file:
            file.write(template_content)

    def save_markers(self):
        with open('data/data.json', 'w', encoding='utf-8') as file:
            json.dump(self.markers, file, ensure_ascii=False, indent=4)

    def runThePage(self):
        self.app.run(host="0.0.0.0", port=8000, debug=True)