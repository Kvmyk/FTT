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

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        self.app.secret_key = "twoj_sekretny_klucz"  # klucz do sesji - niezbędny
        
        # Configure server-side session storage (e.g., filesystem)
        self.app.config['SESSION_TYPE'] = 'filesystem'
        self.app.config['SESSION_PERMANENT'] = True
        self.app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 dzień (sekundy)
        self.app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
        if not os.path.exists(self.app.config['SESSION_FILE_DIR']):
            os.makedirs(self.app.config['SESSION_FILE_DIR'])
        Session(self.app)

        cleanup_thread = threading.Thread(target=self.cleanup_session_files_loop)
        cleanup_thread.daemon = True
        cleanup_thread.start()

        # Domyślne współrzędne (np. Warszawa) - użyte TYLKO gdy user nie ustawił własnych
        self.default_lat = 52.2297
        self.default_lon = 21.0122

        # Ładujemy globalne markery z pliku data.json (toalety)
        self.markers = self.load_markers()

        # Tworzymy na start pustą mapę, ale i tak będziemy ją przeładowywać w update_map()
        self.m = self.create_map()

        self.setup_routes()

    def cleanup_session_files(self):
        session_lifetime = self.app.config.get('PERMANENT_SESSION_LIFETIME', 3600)
        session_dir = self.app.config.get('SESSION_FILE_DIR')
        if not session_dir or not os.path.isdir(session_dir):
            logging.warning("Katalog sesji nie istnieje lub nie jest zdefiniowany.")
            return
        now = time.time()
        for filename in os.listdir(session_dir):
            file_path = os.path.join(session_dir, filename)
            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)
                if (now - file_mtime) > session_lifetime:
                    try:
                        os.remove(file_path)
                        logging.debug(f"Usunięto stary plik sesji: {file_path}")
                    except Exception as e:
                        logging.error(f"Błąd podczas usuwania pliku {file_path}: {e}")

    # Pętla uruchamiana w tle, która co określony czas wywołuje cleanup sesji
    def cleanup_session_files_loop(self):
        cleanup_interval = 3600  # czyszczenie co 1 godzinę
        while True:
            self.cleanup_session_files()
            time.sleep(cleanup_interval)

    def create_map(self, center_lat=None, center_lon=None):
        """
        Tworzy nową instancję folium.Map. 
        Jeśli center_lat/lon są None, użyjemy self.default_lat/lon.
        """
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

    def load_markers(self):
        """Wczytuje listę toalet (markerów) z pliku data.json."""
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

    def save_markers(self):
        """Zapisuje obecne 'globalne' markery do pliku data.json."""
        try:
            with open(os.path.join('data', 'data.json'), 'w', encoding='utf-8') as file:
                json.dump(self.markers, file, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Błąd przy zapisie do data.json: {e}")

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

            # Słownik z danymi usera w sesji
            user_data = session.get(user_id, {})
            if not user_data:
                user_data = {"marker": None, "current_route": None}

            # Zapisz nowy marker użytkownika
            user_marker = {
                "lat": data['lat'],
                "lon": data['lon'],
                "name": "User Location",
                "description": "This is your location"
            }
            user_data["marker"] = user_marker
            session[user_id] = user_data

            # Obliczamy trasę do najbliższego markera
            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if nearest_marker:
                route = get_route(
                    user_marker['lat'], user_marker['lon'],
                    nearest_marker['lat'], nearest_marker['lon']
                )
                if route:
                    self.add_route_to_map(route)

            return jsonify({
                'status': 'success',
                'lat': user_marker['lat'],
                'lon': user_marker['lon']
            })

        @self.app.route('/render_map', methods=['GET'])
        def render_map():
            return self.update_map()

        @self.app.route('/add_comment', methods=['POST'])
        def add_comment():
            data = request.form
            lat = float(data.get('lat'))
            lon = float(data.get('lon'))
            comment = data.get('comment')
            rating = data.get('rating')

            for marker in self.markers:
                if marker['lat'] == lat and marker['lon'] == lon:
                    marker.setdefault('comments', []).append({'comment': comment, 'rating': rating})
                    self.save_markers()
                    return jsonify({'status': 'success'})

            return jsonify({'status': 'error', 'message': 'Marker not found'}), 404

    def add_marker_to_map(self, marker):
        """
        Dodaje POJEDYNCZY marker do mapy self.m.
        """
        if marker.get('name') == "User Location":
            # Marker użytkownika
            icon = folium.CustomIcon(
                user_icon,
                icon_size=(50, 50),
                shadow_size=(50, 50)
            )
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
            iconToilet = folium.CustomIcon(
                toilet_icon, 
                icon_size=(50, 50), 
                shadow_size=(50, 50)
            )
            lat = marker['lat']
            lon = marker['lon']
            popup_content = f"""
                <div style="width: 300px;">
                    <h2>{marker['name']}</h2>
                    <p>{marker.get('description', 'No description')}</p>
                </div>
            """
            folium.Marker(
                location=[lat, lon],
                icon=iconToilet,
                popup=folium.Popup(popup_content, min_width=250, max_height=300)
            ).add_to(self.m)

    def add_route_to_map(self, route):
        """
        Dodaje trasę do mapy
        """
        coordinates = [(coord[1], coord[0]) for coord in route['routes'][0]['geometry']['coordinates']]
        folium.PolyLine(
            locations=coordinates,
            color='#d00000',
            weight=5,
            opacity=0.7
        ).add_to(self.m)

    def update_map(self):
        """
        Buduje nową mapę, centrowaną na markerze użytkownika (jeśli istnieje)
        lub na domyślnych współrzędnych. Następnie dodaje:
          - globalne markery (toalety),
          - marker użytkownika,
          - trasę użytkownika (current_route).
        Zwraca HTML do wstawienia na stronę.
        """
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

    def runThePage(self):
        self.app.run(host="2a01:4f9:2b:289c::130", port=80)

