import os
import folium
import flask
import requests
import geopy
import json
import base64
import uuid
import logging
import threading
import time
from flask_session import Session
from flask import Flask, send_from_directory, jsonify, request, session
from utils import get_coordinates, get_route, find_nearest_marker, haversine, format_distance_text

logging.basicConfig(level=logging.DEBUG)

# Ścieżka do pliku z ikoną (w katalogu static)
toilet_icon = os.path.join('toilet_icon.png')
user_icon = os.path.join('user_icon.png')

class MapManager:
    def __init__(self, default_lat=52.2297, default_lon=21.0122):
        self.default_lat = default_lat
        self.default_lon = default_lon
        self.markers = []
        self.m = None

    def create_map(self, center_lat=None, center_lon=None):
        if center_lat is None:
            center_lat = self.default_lat
        if center_lon is None:
            center_lon = self.default_lon
        return folium.Map(
            location=[center_lat, center_lon],
            tiles="Cartodb positron",
            zoom_start=15,
            overlay=False,
            min_zoom=2,
            max_zoom=18,
            height='100%',
            width='100%',
            max_bounds=True
        )

    def add_marker_to_map(self, marker):
        if marker.get('name') == "User Location":
            icon = folium.CustomIcon(user_icon, icon_size=(50, 50), shadow_size=(50, 50))
            popup_content = f"""
                <div style="width: 300px;">
                    <h2>User Location</h2>
                    <p>{marker.get('description', '')}</p>
                </div>
            """
            folium.Marker(
                location=[marker['lat'], marker['lon']],
                popup=popup_content,
                icon=icon
            ).add_to(self.m)
        else:
            iconToilet = folium.CustomIcon(toilet_icon, icon_size=(50, 50), shadow_size=(50, 50))
            lat = marker['lat']
            lon = marker['lon']
            folium.Marker(
                location=[lat, lon],
                icon=iconToilet,
                popup=folium.Popup(self.generate_marker_popup(marker), min_width=250, max_height=300)
            ).add_to(self.m)

    def generate_marker_popup(self, marker):
        name = marker.get('name', 'Unknown')
        description = marker.get('description', 'No description')
        payable = "TAK" if marker.get('payable', False) else "NIE"
        onlyForClients = "TAK" if marker.get('onlyForClients', False) else "NIE"
        rating = marker.get('rating', 'Brak oceny')
        photo_base64 = marker.get('photo', None)
        comments_list = marker.get('comments', [])
        photo_html = f"""
            <img src="data:image/jpeg;base64,{photo_base64}" 
                 style="max-width: 150px; max-height: 150px; width: auto; height: auto; object-fit: contain; border-radius: 4px; display: block; margin: 10px 0;">
        """ if photo_base64 else ""

        comments_html = f"""
            <div id='comments-container-{marker["lat"]}-{marker["lon"]}'>
                <div id='comments-{marker["lat"]}-{marker["lon"]}'
                     style='max-height: 80px; overflow-y: hidden; font-family: Roboto, sans-serif;'>
                    {self.generate_comments_html(comments_list)}
                </div>
            </div>
        """

        comment_button_html = f"""
            <button onclick="window.parent.openCommentModal({marker['lat']}, {marker['lon']})" 
                    class="popup-button" style="width: 80%; background-color: red; color: white;">
                Dodaj komentarz
            </button>
        """

        return f"""
            <div style="width: 300px; max-height:300px, overflow-y: auto;">
                <h2>{name}</h2>
                <p>{description}</p>
                <p><strong>Płatna:</strong> {payable}</p>
                <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                <p><strong>Ocena:</strong> {rating}</p>
                <div style="display: flex; flex-wrap: wrap; gap: 5px; justify-content: center;">
                    {photo_html}
                </div>
                {comments_html}
                {comment_button_html}
            </div>
        """

    def generate_comments_html(self, comments_list):
        comments_html = ""
        if comments_list:
            first_comment = comments_list[0]
            comments_html += f"""
                <p><strong>Ocena:</strong> {first_comment.get('rating')}</p>
                <p>{first_comment.get('comment')}</p>
            """
            if len(comments_list) > 1:
                for c in comments_list[1:]:
                    comments_html += f"""
                    <hr style="border-top: 1px solid #ccc;" />
                    <p><strong>Ocena:</strong> {c.get('rating')}</p>
                    <p>{c.get('comment')}</p>
                    """
        return comments_html

    def update_map(self):
        user_id = session.get('user_id')
        center_lat = self.default_lat
        center_lon = self.default_lon
        if user_id:
            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if user_marker:
                center_lat = user_marker['lat']
                center_lon = user_marker['lon']

        self.m = self.create_map(center_lat, center_lon)

        for marker in self.markers:
            self.add_marker_to_map(marker)

        if user_id:
            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if user_marker:
                self.add_marker_to_map(user_marker)
            route = user_data.get('current_route')
            if route:
                self.add_route_to_map(route)

        return self.m._repr_html_()

    def add_route_to_map(self, route):
        coordinates = [(coord[1], coord[0]) for coord in route['routes'][0]['geometry']['coordinates']]
        folium.PolyLine(
            locations=coordinates,
            color='#d00000',
            weight=5,
            opacity=0.7
        ).add_to(self.m)

class MarkerManager:
    def __init__(self):
        self.data_changed = False

    def load_markers(self):
        try:
            with open(os.path.join('data', 'data.json'), 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
                else:
                    logging.error("Plik data.json nie zawiera listy.")
                    return []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Problem z wczytaniem pliku data.json: {e}")
            return []

    def save_markers(self, markers):
        if self.data_changed:
            try:
                with open(os.path.join('data', 'data.json'), 'w', encoding='utf-8') as file:
                    json.dump(markers, file, ensure_ascii=False, indent=4)
                self.data_changed = False
            except Exception as e:
                logging.error(f"Błąd przy zapisie do data.json: {e}")

    def add_marker(self, markers, new_marker):
        markers.append(new_marker)
        self.data_changed = True

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        self.app.secret_key = "twoj_sekretny_klucz"
        self.app.config['SESSION_TYPE'] = 'filesystem'
        self.app.config['SESSION_PERMANENT'] = True
        self.app.config['PERMANENT_SESSION_LIFETIME'] = 3600
        self.app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
        if not os.path.exists(self.app.config['SESSION_FILE_DIR']):
            os.makedirs(self.app.config['SESSION_FILE_DIR'])
        Session(self.app)

        self.map_manager = MapManager()
        self.marker_manager = MarkerManager()
        self.markers = self.marker_manager.load_markers()

        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def fullscreen():
            return send_from_directory('static/html', 'template.html')

        @self.app.route('/location', methods=['POST'])
        def location():
            data = request.json
            user_id = session.get('user_id')
            if not user_id:
                user_id = str(uuid.uuid4())
                session['user_id'] = user_id

            user_marker = {
                "lat": data['lat'],
                "lon": data['lon'],
                "name": "User Location",
                "description": "This is your location"
            }
            session['user_marker'] = user_marker

            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if nearest_marker:
                route = get_route(user_marker['lat'], user_marker['lon'], nearest_marker['lat'], nearest_marker['lon'])
                if route:
                    self.map_manager.add_route_to_map(route)

            return jsonify({'status': 'success', 'lat': user_marker['lat'], 'lon': user_marker['lon']})

        @self.app.route('/submit', methods=['POST'])
        def submit():
            data = request.form
            userInput = data.get('userInput', '')
            description = data.get('description', '')
            payable = data.get('payable', 'false').lower() == 'true'
            onlyForClients = data.get('onlyForClients', 'false').lower() == 'true'
            rating = data.get('rating', '0')
            photo = request.files.get('photos')
            photo_base64 = None
            if photo:
                photo_base64 = self.save_photo(photo)

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
                self.marker_manager.add_marker(self.markers, new_marker)
                self.marker_manager.save_markers(self.markers)
                return jsonify({'status': 'success', 'lat': lat, 'lon': lon})
            else:
                return jsonify({'status': 'error', 'message': 'Location not found'})

        @self.app.route('/render_map', methods=['GET'])
        def render_map():
            return self.map_manager.update_map()

    def save_photo(self, photo):
        photo_filename = f"{uuid.uuid4()}.jpg"
        photo_path = os.path.join('static/images', photo_filename)
        photo.save(photo_path)
        with open(photo_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')

    def run(self):
        self.app.run(host="2a01:4f9:2b:289c::130", port=80)
