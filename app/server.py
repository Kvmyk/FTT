import os
import folium
import json
import base64
import uuid
import logging
import threading
import time
import math
from flask import Flask, send_from_directory, jsonify, request, session, render_template_string
from flask_session import Session

from utils import get_coordinates, get_route, find_nearest_marker, haversine, format_distance_text

logging.basicConfig(level=logging.DEBUG)

# Ścieżki do ikon (umieszczonych np. w katalogu static)
TOILET_ICON = os.path.join('toilet_icon.png')
USER_ICON = os.path.join('user_icon.png')

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        self.app.secret_key = "twoj_sekretny_klucz"  # klucz do sesji
        
        # Konfiguracja sesji
        self.app.config['SESSION_TYPE'] = 'filesystem'
        self.app.config['SESSION_PERMANENT'] = True
        self.app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 godzina
        self.app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
        if not os.path.exists(self.app.config['SESSION_FILE_DIR']):
            os.makedirs(self.app.config['SESSION_FILE_DIR'])
        Session(self.app)

        # Lock do synchronizacji dostępu do markerów
        self.markers_lock = threading.Lock()

        self.cleanup_thread = None
        self.start_cleanup_thread()
        
        # Domyślne współrzędne (np. Warszawa)
        self.default_lat = 52.2297
        self.default_lon = 21.0122

        # Ładujemy globalne markery (toalety) z pliku data.json
        self.markers = self.load_markers()

        # Inicjalizacja mapy
        self.m = self.create_map()

        self.setup_routes()
    
    # -------------------
    # Pomocnicze zarządzanie sesją
    # -------------------
    def get_user_data(self):
        """Pobiera lub inicjalizuje dane użytkownika w sesji."""
        if 'user_data' not in session:
            session['user_data'] = {}
        return session['user_data']

    # -------------------
    # Obsługa czyszczenia sesji
    # -------------------
    def start_cleanup_thread(self):
        if not self.cleanup_thread:
            self.cleanup_thread = threading.Thread(target=self.cleanup_session_files_loop, daemon=True)
            self.cleanup_thread.start()

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

    def cleanup_session_files_loop(self):
        cleanup_interval = 3600  # co godzinę
        while True:
            self.cleanup_session_files()
            time.sleep(cleanup_interval)

    # -------------------
    # Operacje na mapie
    # -------------------
    def create_map(self, center_lat=None, center_lon=None):
        """Tworzy nową instancję mapy."""
        if center_lat is None:
            center_lat = self.default_lat
        if center_lon is None:
            center_lon = self.default_lon

        return folium.Map(
            location=[center_lat, center_lon],
            tiles="Cartodb positron",
            zoom_start=15,
            min_zoom=10,
            max_zoom=18,
            max_bounds=True
        )

    def update_map(self):
        """Aktualizuje mapę na podstawie danych sesji i markerów."""
        user_data = self.get_user_data()
        center_lat = self.default_lat
        center_lon = self.default_lon
        if 'marker' in user_data:
            center_lat = user_data['marker']['lat']
            center_lon = user_data['marker']['lon']
        
        # Tworzymy nową mapę
        self.m = self.create_map(center_lat, center_lon)
        
        # Dodajemy markery toalet
        with self.markers_lock:
            for marker in self.markers:
                self.add_marker_to_map(marker)
        # Dodajemy marker użytkownika
        if 'marker' in user_data:
            self.add_marker_to_map(user_data['marker'])

        # Rysujemy trasę, jeśli istnieje
        if 'current_route' in user_data and user_data['current_route']:
            route = user_data['current_route']
            coordinates = [
                (coord[1], coord[0])
                for coord in route['routes'][0]['geometry']['coordinates']
            ]
            distance = route['routes'][0]['distance']
            distance_text = f"{distance / 1000:.2f} km"
            
            folium.PolyLine(
                locations=coordinates,
                color='#d00000',
                weight=5,
                opacity=0.7
            ).add_to(self.m)
            
            mid_point_index = len(coordinates) // 2
            mid_point = coordinates[mid_point_index]
            offset_lat = 0.0007
            offset_lon = 0.0007
            mid_point_offset = [mid_point[0] + offset_lat, mid_point[1] + offset_lon]
            
            folium.Marker(
                location=mid_point_offset,
                icon=folium.DivIcon(
                    html=f"""
                        <div style="
                            font-size: 14px; 
                            color: #D32F2F;
                            font-weight: bold;
                            background-color: rgba(255, 255, 255, 0.9);
                            padding: 0.4em 0.8em;
                            border-radius: 0.3em;
                            text-align: center;
                        ">
                            {distance_text}
                        </div>
                    """
                )
            ).add_to(self.m)
        
        return self.m._repr_html_()

    def add_route_to_map(self, route):
        """Zapisuje trasę w danych użytkownika i aktualizuje mapę."""
        user_data = self.get_user_data()
        user_data['current_route'] = route
        session['user_data'] = user_data
        self.update_map()

    # -------------------
    # Operacje na markerach
    # -------------------
    def add_marker_to_map(self, marker):
        """Dodaje pojedynczy marker do mapy."""
        if self.m is None:
            self.m = self.create_map()
        
        # Sprawdzamy, czy marker to lokalizacja użytkownika
        if marker.get('name') == "User Location":
            icon = folium.CustomIcon(
                USER_ICON,
                icon_size=(50, 50)
            )
            popup_html = self.generate_popup_html(marker, is_within_range=True)
            folium.Marker(
                location=[marker['lat'], marker['lon']],
                popup=popup_html,
                icon=icon
            ).add_to(self.m)
        else:
            # Dla markerów toalet
            user_data = self.get_user_data()
            user_marker = user_data.get('marker')
            is_within_range = False
            if user_marker:
                distance = haversine(user_marker['lat'], user_marker['lon'], marker['lat'], marker['lon'])
                distance_km = distance / 1000
                is_within_range = distance_km <= 10

            icon = folium.CustomIcon(
                TOILET_ICON,
                icon_size=(50, 50)
            )
            popup_html = self.generate_popup_html(marker, is_within_range)
            folium.Marker(
                location=[marker['lat'], marker['lon']],
                popup=popup_html,
                icon=icon
            ).add_to(self.m)

    def generate_popup_html(self, marker, is_within_range):
        """
        Generuje HTML dla popupu markera toalety,
        zawierający sekcję komentarzy oraz przycisk dodawania komentarza.
        """
        # Dane podstawowe
        name = marker.get("name", "Unknown")
        description = marker.get("description", "No description")
        payable = "TAK" if marker.get("payable", False) else "NIE"
        onlyForClients = "TAK" if marker.get("onlyForClients", False) else "NIE"
        rating = marker.get("rating", "Brak oceny")
        photo_base64 = marker.get("photo")
        photo_html = ""
        if photo_base64:
            photo_html = (
                f'<img src="data:image/jpeg;base64,{photo_base64}" '
                f'style="max-width:150px; max-height:150px; object-fit:contain; '
                f'border-radius:4px; display:block; margin:10px auto;">'
            )
        
        # Przycisk nawigacji ("Nawiguj")
        navigate_button_html = f"""
        <button onclick="window.parent.navigateToToilet({marker['lat']}, {marker['lon']})"
                style="
                    opacity: {'1' if is_within_range else '0.7'};
                    pointer-events: {'auto' if is_within_range else 'none'};
                    filter: {'none' if is_within_range else 'brightness(0.8)'};
                    width: 80%;
                    background-color: red;
                    color: white;
                    padding: 14px 20px;
                    margin: 8px 0;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-family: 'Roboto', sans-serif;
                    font-weight: 300;
                    transition: all 0.3s ease;
                "
                onmouseover="this.style.backgroundColor='#C92704'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)'"
                onmouseout="this.style.backgroundColor='red'; this.style.transform='none'; this.style.boxShadow='none'">
            Nawiguj
        </button>
        """
        
        # Sekcja komentarzy
        comments_list = marker.get("comments", [])
        comments_html = f"""
        <div id="comments-container-{marker['lat']}-{marker['lon']}">
            <div id="comments-{marker['lat']}-{marker['lon']}"
                style="max-height: 80px; overflow-y: hidden; font-family: Roboto, sans-serif;
                        scrollbar-width: thin; scrollbar-color: #888 #f1f1f1; padding-right: 5px;
                        -webkit-scrollbar-width: thin; -webkit-scrollbar-color: #888 #f1f1f1;">
                <style>
                    #comments-{marker['lat']}-{marker['lon']}::-webkit-scrollbar {{
                        width: 8px;
                    }}
                    #comments-{marker['lat']}-{marker['lon']}::-webkit-scrollbar-track {{
                        background: #f1f1f1;
                        border-radius: 4px;
                    }}
                    #comments-{marker['lat']}-{marker['lon']}::-webkit-scrollbar-thumb {{
                        background: #888;
                        border-radius: 4px;
                    }}
                    #comments-{marker['lat']}-{marker['lon']}::-webkit-scrollbar-thumb:hover {{
                        background: #555;
                    }}
                </style>
        """
        # Jeśli są jakieś komentarze – wyświetlamy pierwszy oraz (jeśli więcej) kolejne z podziałem linią
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
        comments_html += "</div>"
        
        # Jeśli jest więcej niż jeden komentarz – dodajemy przycisk rozwijania listy
        if len(comments_list) > 1:
            comments_html += f"""
                <button onclick="
                    var commentsDiv = document.getElementById('comments-{marker['lat']}-{marker['lon']}');
                    var arrow = this.querySelector('span');
                    if (commentsDiv.style.maxHeight === '80px') {{
                        commentsDiv.style.maxHeight = '200px';
                        commentsDiv.style.overflowY = 'scroll';
                        arrow.textContent = '▲';
                    }} else {{
                        commentsDiv.style.maxHeight = '80px';
                        commentsDiv.style.overflowY = 'hidden';
                        arrow.textContent = '▼';
                    }}"
                    style="width: auto; background: none; color: #666; padding: 4px 8px;
                        margin: 2px 0; border: none; cursor: pointer;
                        font-family: 'Roboto', sans-serif; font-size: 12px;">
                    <span>▼</span> Więcej komentarzy
                </button>
            """
        comments_html += "</div>"
        
        # Przycisk "Dodaj komentarz" (używamy współrzędnych jako identyfikatora)
        comment_button_html = f"""
        <button onclick="window.parent.openCommentModal({marker['lat']}, {marker['lon']})"
                class="popup-button"
                style="
                    width: 80%;
                    background-color: red;
                    color: white;
                    padding: 14px 20px;
                    margin: 8px 0;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-family: 'Roboto', sans-serif;
                    font-weight: 300;
                    transition: all 0.3s ease;
                "
                onmouseover="this.style.backgroundColor='#C92704'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)'"
                onmouseout="this.style.backgroundColor='red'; this.style.transform='none'; this.style.boxShadow='none'">
            Dodaj komentarz
        </button>
        """
        
        # Formatowanie całego popupu:
        if comments_list:
            wholePopUp = f"""
            <div style="width: 300px; max-height:300px; overflow-y: auto;">
                <h2>{name}</h2>
                <p>{description}</p>
                <p><strong>Płatna:</strong> {payable}</p>
                <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                <p><strong>Ocena:</strong> {rating}</p>
                <div style="display: flex; flex-wrap: wrap; gap: 5px; justify-content: center;">
                    {photo_html}
                </div>
                <h3 style="margin-top: 0;">Komentarze</h3>
                {comments_html}
                {navigate_button_html}
                {comment_button_html}
            </div>
            """
        else:
            wholePopUp = f"""
            <div style="width: 300px; max-height:300px; overflow-y: auto;">
                <h2>{name}</h2>
                <p>{description}</p>
                <p><strong>Płatna:</strong> {payable}</p>
                <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                <p><strong>Ocena:</strong> {rating}</p>
                <div style="display: flex; flex-wrap: wrap; gap: 5px; justify-content: center;">
                    {photo_html}
                </div>
                {navigate_button_html}
                {comment_button_html}
            </div>
            """
        return wholePopUp

    def load_markers(self):
        """Wczytuje listę markerów z pliku data/data.json."""
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
        """Zapisuje aktualne markery do pliku data/data.json."""
        try:
            with self.markers_lock:
                with open(os.path.join('data', 'data.json'), 'w', encoding='utf-8') as file:
                    json.dump(self.markers, file, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Błąd przy zapisie do data.json: {e}")

    # -------------------
    # Definicja endpointów
    # -------------------
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return send_from_directory('static/html', 'template.html')

        @self.app.route('/location', methods=['POST'])
        def location():
            data = request.json
            user_data = self.get_user_data()
            
            user_marker = {
                "lat": data['lat'],
                "lon": data['lon'],
                "name": "User Location",
                "description": "This is your location"
            }
            user_data["marker"] = user_marker
            session['user_data'] = user_data

            # Wyznaczanie trasy do najbliższego markera
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

        @self.app.route('/nearest_toilet_distance', methods=['GET'])
        def nearest_toilet_distance():
            user_data = self.get_user_data()
            user_marker = user_data.get('marker')
            if not user_marker:
                response = jsonify({
                    'status': 'pending',
                    'message': 'Czekaj, pobieranie lokalizacji...'
                })
                response.headers['Cache-Control'] = 'no-store'
                return response, 202

            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if not nearest_marker:
                response = jsonify({'status': 'error', 'message': 'No toilets found'})
                response.headers['Cache-Control'] = 'no-store'
                return response, 404

            route = get_route(
                user_marker['lat'], user_marker['lon'],
                nearest_marker['lat'], nearest_marker['lon']
            )
            if not route:
                response = jsonify({'status': 'error', 'message': 'Route not found'})
                response.headers['Cache-Control'] = 'no-store'
                return response, 404

            distance = route['routes'][0]['distance']
            response = jsonify({
                'status': 'success',
                'distance': f"{distance / 1000:.2f} km",
                'name': nearest_marker.get('name', 'Toaleta bez nazwy')
            })
            response.headers['Cache-Control'] = 'no-store'
            return response, 200

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
                photo_base64 = base64.b64encode(photo.read()).decode('utf-8')

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
                with self.markers_lock:
                    self.markers.append(new_marker)
                    self.save_markers()

                # Aktualizacja mapy
                self.update_map()

                # Wyznaczenie trasy do najbliższego markera, jeśli użytkownik podał swoją lokalizację
                user_data = self.get_user_data()
                user_marker = user_data.get('marker')
                if user_marker:
                    nearest_marker = find_nearest_marker(user_marker, self.markers)
                    if nearest_marker:
                        route = get_route(
                            user_marker['lat'], user_marker['lon'],
                            nearest_marker['lat'], nearest_marker['lon']
                        )
                        if route:
                            self.add_route_to_map(route)

                return jsonify({'status': 'success', 'lat': lat, 'lon': lon})
            else:
                return jsonify({'status': 'error', 'message': 'Location not found'})

        @self.app.route('/add_comment', methods=['POST'])
        def add_comment():
            data = request.form
            lat = float(data.get('lat'))
            lon = float(data.get('lon'))
            comment = data.get('comment')
            rating = data.get('rating')

            found = False
            with self.markers_lock:
                for marker in self.markers:
                    # Używamy math.isclose do porównania współrzędnych
                    if math.isclose(marker['lat'], lat, rel_tol=1e-5) and math.isclose(marker['lon'], lon, rel_tol=1e-5):
                        marker.setdefault('comments', []).append({'comment': comment, 'rating': rating})
                        self.save_markers()
                        found = True
                        break
            if found:
                return jsonify({'status': 'success'})
            else:
                return jsonify({'status': 'error', 'message': 'Marker not found'}), 404

        @self.app.route('/navigate', methods=['POST'])
        def navigate():
            data = request.json
            user_data = self.get_user_data()
            
            user_marker = {
                "lat": data['user_lat'],
                "lon": data['user_lon'],
                "name": "User Location",
                "description": "This is your location"
            }
            user_data['marker'] = user_marker

            route = get_route(
                data['user_lat'], 
                data['user_lon'],
                data['target_lat'], 
                data['target_lon']
            )
            
            if route:
                user_data['current_route'] = route
                session['user_data'] = user_data
                self.update_map()
                return jsonify({'status': 'success'})
            
            return jsonify({'status': 'error', 'message': 'Could not calculate route'})

        @self.app.route('/render_map', methods=['GET'])
        def render_map():
            return self.update_map()

        @self.app.after_request
        def add_header(response):
            response.headers['Cache-Control'] = 'no-store'
            return response

    def runThePage(self):
        self.app.run(host = "2a01:4f9:2b:289c::130", port=80)
