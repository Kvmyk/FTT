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
import sqlite3
import datetime
from flask_session import Session
from flask_compress import Compress
from flask import Flask, send_from_directory, jsonify, request, session
from utils import get_coordinates, get_route, find_nearest_marker, haversine, format_distance_text, is_hate_speech, isInOpoleProvince
from dotenv import load_dotenv
from contextlib import closing

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

# Ścieżka do pliku z ikoną (w katalogu static)
toilet_icon = os.path.join('toilet_icon.png')
user_icon = os.path.join('user_icon.png')

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        Compress(self.app)
        self.app.secret_key = os.environ.get('KEY')  # klucz do sesji - niezbędny
        
        # Configure server-side session storage (e.g., filesystem)
        self.app.config['SESSION_TYPE'] = 'filesystem'
        self.app.config['SESSION_PERMANENT'] = True
        self.app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 godzina (sekundy)
        self.app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
        if not os.path.exists(self.app.config['SESSION_FILE_DIR']):
            os.makedirs(self.app.config['SESSION_FILE_DIR'])
        Session(self.app)

        self.cleanup_thread = None
        self.start_cleanup_thread()
        
        # Domyślne współrzędne (np. Warszawa) - użyte TYLKO gdy user nie ustawił własnych
        self.default_lat = 52.2297
        self.default_lon = 21.0122

        # Setup database
        self.setup_database()
        
        # Ładujemy globalne markery z bazy danych (toalety)
        self.markers = self.load_markers()
        self.original_markers = self.markers.copy()  # Przechowujemy oryginalną listę markerów

        # Inicjalizacja mapy jako None
        self.m = None

        self.setup_routes()
        self.setup_database()
    
    def start_cleanup_thread(self):
        if not self.cleanup_thread:
            self.cleanup_thread = threading.Thread(target=self.cleanup_session_files_loop)
            self.cleanup_thread.daemon = True
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

    # Pętla uruchamiana w tle, która co określony czas wywołuje cleanup sesji
    def cleanup_session_files_loop(self):
        cleanup_interval = 3600  # czyszczenie co 1 godzinę
        while True:
            self.cleanup_session_files()
            time.sleep(cleanup_interval)

    def create_map(self, center_lat=None, center_lon=None):
        """Tworzy nową instancję mapy, usuwając starą"""
        if hasattr(self, 'm') and self.m is not None:
            del self.m  # Explicitly delete old map
            self.m = None
            
        if center_lat is None:
            center_lat = self.default_lat
        if center_lon is None:
            center_lon = self.default_lon

        self.m = folium.Map(
            location=[center_lat, center_lon],
            tiles="Cartodb positron",
            zoom_start=15,
            overlay=False,
            min_zoom=10,
            max_zoom=18,
            height='100%',
            width='100%',
            max_bounds=True
        )
        return self.m


    def load_markers(self):
        """Loads toilet markers from SQLite database."""
        try:
            markers = []
            with closing(sqlite3.connect('toilets.db')) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS toilets (
                    id INTEGER PRIMARY KEY,
                    lat REAL,
                    lon REAL,
                    name TEXT,
                    description TEXT,
                    payable INTEGER,
                    onlyForClients INTEGER,
                    forDisabled INTEGER,
                    rating REAL,
                    base_rating REAL,
                    photos TEXT,
                    comments TEXT,
                    openingHours TEXT
                )
                ''')
                
                # Check if we need to add the openingHours column
                cursor.execute("PRAGMA table_info(toilets)")
                columns = [col[1] for col in cursor.fetchall()]
                if "openingHours" not in columns:
                    cursor.execute("ALTER TABLE toilets ADD COLUMN openingHours TEXT")
                    conn.commit()
                
                cursor.execute('SELECT * FROM toilets')
                rows = cursor.fetchall()
                
                for row in rows:
                    try:
                        photos = json.loads(row['photos']) if row['photos'] else []
                    except:
                        photos = []
                        
                    try:
                        comments = json.loads(row['comments']) if row['comments'] else []
                    except:
                        comments = []
                        
                    try:
                        opening_hours = json.loads(row['openingHours']) if row['openingHours'] else {"is24h": False, "schedule": {}}
                    except:
                        opening_hours = {"is24h": False, "schedule": {}}
                    
                    markers.append({
                        'lat': row['lat'],
                        'lon': row['lon'],
                        'name': row['name'],
                        'description': row['description'],
                        'payable': bool(row['payable']),
                        'onlyForClients': bool(row['onlyForClients']),
                        'forDisabled': bool(row['forDisabled']),
                        'rating': row['rating'],
                        'base_rating': row['base_rating'],
                        'photos': photos,
                        'comments': comments,
                        'openingHours': opening_hours
                    })
                    
            self.markers = markers
            self.original_markers = markers
            logging.info(f"Successfully loaded {len(markers)} markers from database")
            return markers
        except Exception as e:
            logging.error(f"Error loading markers from database: {str(e)}")
            return []

    def save_markers(self):
        """Save markers to SQLite database."""
        try:
            with closing(sqlite3.connect('toilets.db')) as conn:
                conn.execute('''
                CREATE TABLE IF NOT EXISTS toilets (
                    id INTEGER PRIMARY KEY,
                    lat REAL,
                    lon REAL,
                    name TEXT,
                    description TEXT,
                    payable INTEGER,
                    onlyForClients INTEGER,
                    forDisabled INTEGER,
                    rating REAL,
                    base_rating REAL,
                    photos TEXT,
                    comments TEXT,
                    openingHours TEXT
                )
                ''')
                
                conn.execute('DELETE FROM toilets')
                
                for marker in self.original_markers:
                    photos_json = json.dumps(marker.get('photos', []))
                    comments_json = json.dumps(marker.get('comments', []))
                    opening_hours_json = json.dumps(marker.get('openingHours', {"is24h": False, "schedule": {}}))
                    
                    conn.execute(
                        'INSERT INTO toilets (lat, lon, name, description, payable, onlyForClients, forDisabled, rating, base_rating, photos, comments, openingHours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (
                            marker['lat'],
                            marker['lon'],
                            marker.get('name', ''),
                            marker.get('description', ''),
                            1 if marker.get('payable', False) else 0,
                            1 if marker.get('onlyForClients', False) else 0,
                            1 if marker.get('forDisabled', False) else 0,
                            marker.get('rating', 0),
                            marker.get('base_rating', marker.get('rating', 0)),
                            photos_json,
                            comments_json,
                            opening_hours_json
                        )
                    )
                
                conn.commit()
                logging.info(f"Successfully saved {len(self.original_markers)} markers to database")
        except Exception as e:
            logging.error(f"Error saving markers to database: {str(e)}")

    def setup_routes(self):
        @self.app.route('/')
        def fullscreen():
            """
            Serwujemy główny plik HTML (np. /static/html/template.html),
            który wczytuje JS i następnie dociąga /render_map w div#map.
            """
            return send_from_directory('static/html', 'template.html')

        @self.app.route('/location', methods=['POST'])
        def location():
            """
            Otrzymuje JSON z danymi {lat, lon} i zapisuje je w sesji użytkownika 
            jako 'marker' (lokatę usera). Następnie oblicza trasę do najbliższej toalety.
            """
            data = request.json
            # Pobierz/utwórz unikalne user_id
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

            # Pobierz filtry z sesji
            filters = user_data.get('filters', {})
            filter_payable = filters.get('filterPayable', False)
            filter_for_clients = filters.get('filterForClients', False)
            filter_for_disabled = filters.get('filterForDisabled', False)
            filter_rating = float(filters.get('filterRating', 0))

            # Sprawdź czy użytkownik jest w woj. opolskim
            if not isInOpoleProvince(data['lat'], data['lon']):
                logging.warning("Użytkownik poza województwem opolskim - nie generuję trasy.")
                user_data['current_route'] = None
                session[user_id] = user_data
                return jsonify({
                    'status': 'success',
                    'lat': user_marker['lat'],
                    'lon': user_marker['lon']
                })

            # Filtrowanie markerów i generowanie trasy tylko dla użytkowników z woj. opolskiego
            markers_to_search = self.original_markers
            if filter_payable or filter_for_clients or filter_for_disabled or filter_rating > 0:
                markers_to_search = [
                    marker for marker in self.original_markers
                    if (not filter_payable or marker.get('payable', False)) and
                       (not filter_for_clients or marker.get('onlyForClients', False)) and
                       (not filter_for_disabled or marker.get('forDisabled', False)) and
                       (float(marker.get('rating', 0)) >= filter_rating)
                ]

            # Obliczamy trasę TYLKO dla użytkowników z woj. opolskiego
            nearest_marker = find_nearest_marker(user_marker, markers_to_search)
            if nearest_marker:
                # Sprawdź, czy najbliższy marker jest również w województwie opolskim
                if not isInOpoleProvince(nearest_marker['lat'], nearest_marker['lon']):
                    logging.warning("Najbliższy marker poza województwem opolskim - nie generuję trasy.")
                    user_data['current_route'] = None
                    session[user_id] = user_data
                else:
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
            """
            Dodatkowy endpoint, który zwraca odległość do najbliższej toalety.
            """
            user_id = session.get('user_id')
            if not user_id:
                user_id = str(uuid.uuid4())
                session['user_id'] = user_id

            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if not user_marker:
                response = jsonify({
                    'status': 'pending',
                    'message': 'Czekaj, pobieranie lokalizacji...'
                })
                response.headers['Cache-Control'] = 'no-store'
                return response, 202

            # Pobierz filtry z sesji
            filters = user_data.get('filters', {})
            filter_payable = filters.get('filterPayable', False)
            filter_for_clients = filters.get('filterForClients', False)
            filter_for_disabled = filters.get('filterForDisabled', False)
            filter_rating = float(filters.get('filterRating', 0))

            # Filtrowanie markerów
            markers_to_search = self.original_markers
            if filter_payable or filter_for_clients or filter_for_disabled or filter_rating > 0:
                markers_to_search = [
                    marker for marker in self.original_markers
                    if (not filter_payable or marker.get('payable', False)) and
                       (not filter_for_clients or marker.get('onlyForClients', False)) and
                       (not filter_for_disabled or marker.get('forDisabled', False)) and
                       (float(marker.get('rating', 0)) >= filter_rating)
                ]

            nearest_marker = find_nearest_marker(user_marker, markers_to_search)
            if not nearest_marker:
                response = jsonify({'status': 'error', 'message': 'No toilets found'})
                response.headers['Cache-Control'] = 'no-store'
                return response, 404
            
            if not isInOpoleProvince(nearest_marker['lat'], nearest_marker['lon']):
                                    logging.warning("Marker poza województwem opolskim – nie generuję trasy.")
                                    user_data['current_route'] = None
                                    session[user_id] = user_data
                                    route = None
            else:
                route = get_route(user_marker['lat'], user_marker['lon'], nearest_marker['lat'], nearest_marker['lon'])
            if route:
                distance = route['routes'][0]['distance']  # w metrach
                duration = route['routes'][0]['duration'] / 60  # w minutach
                distance_text = format_distance_text(distance)
                return jsonify({
                    'status': 'success',
                    'distance': distance_text,
                    'duration': f"{duration:.0f}",
                    'name': nearest_marker['name'],
                    'nearest_pin_lat': nearest_marker['lat'],
                    'nearest_pin_lon': nearest_marker['lon']
                })  
            else:
                return jsonify({'status': 'error', 'message': 'Route not found'}), 404

        @self.app.route('/submit', methods=['POST'])
        def submit():
            """Handles form submissions for new toilet markers."""
            try:
                userInput = request.form.get('userInput')
                description = request.form.get('description')
                payable = request.form.get('payable') == 'true'
                onlyForClients = request.form.get('onlyForClients') == 'true'
                forDisabled = request.form.get('forDisabled') == 'true'
                rating = request.form.get('rating')
                useUserLocation = request.form.get('useUserLocation') == 'true'
                
                # Parse opening hours JSON
                opening_hours_json = request.form.get('openingHours')
                opening_hours = json.loads(opening_hours_json) if opening_hours_json else {"is24h": False, "schedule": {}}

                # Validate input
                if not userInput or not description or not rating:
                    return jsonify({'status': 'error', 'message': 'Missing required fields'})

                if useUserLocation:
                    user_id = session.get('user_id')
                    if not user_id:
                        return jsonify({'status': 'error', 'message': 'User location is not set'}), 400

                    user_data = session.get(user_id, {})
                    user_marker = user_data.get('marker')
                    if not user_marker:
                        return jsonify({'status': 'error', 'message': 'User location is not set'}), 400

                    lat = user_marker['lat']
                    lon = user_marker['lon']
                else:
                    lat, lon = get_coordinates(userInput)
                    if not lat or not lon:
                        return jsonify({'status': 'error', 'message': 'Nie udało się ustalić współrzędnych.'})

                # Process photos if any
                photos = []
                if 'photos' in request.files:
                    photo_files = request.files.getlist('photos')
                    for file in photo_files:
                        if file and allowed_file(file.filename):
                            # Convert to base64 for storage
                            file_data = file.read()
                            encoded_string = base64.b64encode(file_data).decode('utf-8')
                            photos.append(encoded_string)

                # Create new marker
                new_marker = {
                    'lat': lat,
                    'lon': lon,
                    'name': userInput,
                    'description': description,
                    'payable': payable,
                    'onlyForClients': onlyForClients,
                    'forDisabled': forDisabled,
                    'rating': float(rating),
                    'photos': photos,
                    'openingHours': opening_hours
                }

                # Add marker to the list and save
                self.markers.append(new_marker)
                self.original_markers.append(new_marker)
                self.save_markers()

                # Update map with the new marker
                self.add_marker_to_map(new_marker)
                self.update_map()

                # Success!
                return jsonify({'status': 'success'})
            except Exception as e:
                logging.error(f"Error in submit handler: {str(e)}")
                return jsonify({'status': 'error', 'message': str(e)})

        @self.app.route('/add_comment', methods=['POST'])
        def add_comment():
            data = request.form
            lat = float(data.get('lat'))
            lon = float(data.get('lon'))
            comment = data.get('comment')
            rating = data.get('rating')

            with closing(sqlite3.connect('data/toilets.db')) as conn:
                with closing(conn.cursor()) as cursor:
                    # Find the toilet by coordinates
                    cursor.execute(
                        'SELECT id, rating, base_rating FROM toilets WHERE lat = ? AND lon = ?',
                        (lat, lon)
                    )
                    toilet = cursor.fetchone()
                    
                    if toilet:
                        toilet_id, current_rating, base_rating = toilet
                        
                        # Insert comment
                        cursor.execute(
                            'INSERT INTO comments (toilet_id, comment, rating) VALUES (?, ?, ?)',
                            (toilet_id, comment, rating)
                        )
                        
                        # Update toilet rating
                        cursor.execute(
                            'SELECT AVG(rating) FROM comments WHERE toilet_id = ?',
                            (toilet_id,)
                        )
                        avg_comment_rating = cursor.fetchone()[0] or 0
                        
                        if not base_rating:
                            cursor.execute(
                                'UPDATE toilets SET base_rating = ? WHERE id = ?',
                                (current_rating or rating, toilet_id)
                            )
                            base_rating = current_rating or float(rating)
                        
                        # Get count of comments
                        cursor.execute(
                            'SELECT COUNT(*) FROM comments WHERE toilet_id = ?',
                            (toilet_id,)
                        )
                        comment_count = cursor.fetchone()[0]
                        
                        # Calculate new rating
                        computed_rating = (float(base_rating) + float(avg_comment_rating) * comment_count) / (1 + comment_count)
                        
                        # Update toilet rating
                        cursor.execute(
                            'UPDATE toilets SET rating = ? WHERE id = ?',
                            (computed_rating, toilet_id)
                        )
                        
                        conn.commit()
                        
                        # Update our in-memory markers
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({'status': 'success'})
                    
            return jsonify({'status': 'error', 'message': 'Marker not found'}), 404

        @self.app.route('/navigate', methods=['POST'])
        def navigate():
            data = request.json
            user_id = session.get('user_id')
            
            if not user_id:
                user_id = str(uuid.uuid4())
                session['user_id'] = user_id
            
            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if not user_marker:
                return jsonify({'status': 'error', 'message': 'User location is not set'}), 400
            
            # Check if target is in Opole province
            if not isInOpoleProvince(data['target_lat'], data['target_lon']):
                return jsonify({'status': 'error', 'message': 'Target location is outside Opole province'}), 400
            
            target_marker = next((marker for marker in self.markers 
                         if marker['lat'] == data['target_lat'] 
                         and marker['lon'] == data['target_lon']), None)
            target_name = target_marker['name'] if target_marker else 'Unknown'

            # Calculate route
            route = get_route(
                user_marker['lat'], 
                user_marker['lon'],
                data['target_lat'], 
                data['target_lon']
            )
            
            if route:
                # Save the selected route and target in session
                user_data['current_route'] = route
                user_data['selected_target'] = {
                    'lat': data['target_lat'],
                    'lon': data['target_lon'],
                    'time': time.time()  # Add timestamp for potential cleanup later
                }
                session[user_id] = user_data
                
                # Update map with new route
                self.update_map()
                
                # Return route details
                distance = route['routes'][0]['distance']  # in meters
                duration = route['routes'][0]['duration'] / 60  # in minutes
                distance_text = format_distance_text(distance)
                
                return jsonify({
                    'status': 'success',
                    'distance': distance_text,
                    'duration': f"{duration:.0f}",
                    'name': target_name
                })
            
            return jsonify({'status': 'error', 'message': 'Could not calculate route'}), 404

        @self.app.route('/apply_filters', methods=['POST'])
        def apply_filters():
            data = request.json
            filter_payable = data.get('filterPayable', False)
            filter_for_clients = data.get('filterForClients', False)
            filter_for_disabled = data.get('filterForDisabled', False)
            filter_rating = float(data.get('filterRating', 0))

            user_id = session.get('user_id')
            if user_id:
                user_data = session.get(user_id, {})
                user_data['filters'] = {
                    'filterPayable': filter_payable,
                    'filterForClients': filter_for_clients,
                    'filterForDisabled': filter_for_disabled,
                    'filterRating': filter_rating
                }
                
                # Sprawdź czy użytkownik jest poza województwem opolskim
                user_marker = user_data.get('marker')
                if user_marker and not isInOpoleProvince(user_marker['lat'], user_marker['lon']):
                    # Jeśli użytkownik jest poza województwem, usuń trasę
                    user_data['current_route'] = None
                    logging.warning("Użytkownik poza województwem opolskim - usunięto trasę po zastosowaniu filtrów.")
                
                # Sprawdź czy cel nawigacji jest poza województwem opolskim
                selected_target = user_data.get('selected_target')
                if selected_target and not isInOpoleProvince(selected_target['lat'], selected_target['lon']):
                    # Jeśli cel jest poza województwem, usuń trasę i cel
                    user_data['current_route'] = None
                    user_data['selected_target'] = None
                    logging.warning("Cel nawigacji poza województwem opolskim - usunięto trasę po zastosowaniu filtrów.")
                
                # Zastosuj filtry do markerów, aby sprawdzić czy cel nadal istnieje
                if selected_target:
                    filtered_markers = [
                        marker for marker in self.original_markers
                        if (not filter_payable or marker.get('payable', False)) and
                           (not filter_for_clients or marker.get('onlyForClients', False)) and
                           (not filter_for_disabled or marker.get('forDisabled', False)) and
                           (self.safe_float(marker.get('rating', 0)) >= filter_rating)
                    ]
                    
                    # Sprawdź czy cel nawigacji nadal istnieje po filtrowaniu
                    target_exists = any(
                        abs(marker['lat'] - selected_target['lat']) < 0.0001 and 
                        abs(marker['lon'] - selected_target['lon']) < 0.0001
                        for marker in filtered_markers
                    )
                    
                    if not target_exists:
                        # Cel nawigacji nie istnieje po filtrowaniu, usuwamy trasę i cel
                        user_data['current_route'] = None
                        user_data['selected_target'] = None
                        logging.warning("Cel nawigacji nie istnieje po zastosowaniu filtrów - usunięto trasę.")
                
                session[user_id] = user_data

            self.update_map()

            return jsonify({'status': 'success'})

        @self.app.route('/check_profanity', methods=['POST'])
        def check_profanity():
            data = request.json
            text = data.get('text', '')

            # Tutaj dodaj logikę sprawdzania mowy nienawiści za pomocą modelu AI
            # Na potrzeby przykładu zakładamy, że funkcja `is_hate_speech` sprawdza mowę nienawiści
            if is_hate_speech(text):
                return jsonify({'status': 'hate'})
            else:
                return jsonify({'status': 'neutral'})

        @self.app.route('/navigate_toilet_distance', methods=['POST'])
        def navigate_toilet_distance():
            data = request.json
            user_lat = data.get('user_lat')
            user_lon = data.get('user_lon')
            target_lat = data.get('target_lat')
            target_lon = data.get('target_lon')
            
            if target_lat is None or target_lon is None:
                return jsonify({'status': 'error', 'message': 'Invalid target coordinates'}), 400

            if not isInOpoleProvince(target_lat, target_lon):
                route = None
            else:
                route = get_route(user_lat, user_lon, target_lat, target_lon)
            if route:
                distance = route['routes'][0]['distance']  # w metrach
                duration = route['routes'][0]['duration'] / 60  # w minutach
                distance_text = format_distance_text(distance)

                target_marker = next((marker for marker in self.markers if marker['lat'] == target_lat and marker['lon'] == target_lon), None)
                target_name = target_marker['name'] if target_marker else 'Unknown'
                return jsonify({
                    'status': 'success',
                    'distance': distance_text,
                    'duration': f"{duration:.0f}",
                    'name': target_name
                })
            else:
                return jsonify({'status': 'error', 'message': 'Route not found'}), 404

        @self.app.route('/check_marker_exists', methods=['POST'])
        def check_marker_exists():
            """Sprawdza czy marker istnieje na mapie po zastosowaniu filtrów"""
            data = request.json
            lat = data.get('lat')
            lon = data.get('lon')

                # Jeśli nie ma współrzędnych, zwróć False - marker nie może istnieć bez współrzędnych
            if lat is None or lon is None:
                return jsonify({'exists': False})
        

            # Pobierz filtry z sesji użytkownika
            user_id = session.get('user_id')
            user_data = session.get(user_id, {})
            filters = user_data.get('filters', {})
            
            # Zastosuj filtry do markerów
            filtered_markers = self.markers
            if filters:
                filtered_markers = [
                    marker for marker in self.markers
                    if (not filters.get('filterPayable', False) or marker.get('payable', False)) and
                       (not filters.get('filterForClients', False) or marker.get('onlyForClients', False)) and
                       (not filters.get('filterForDisabled', False) or marker.get('forDisabled', False)) and
                       (self.safe_float(marker.get('rating', 0)) >= self.safe_float(filters.get('filterRating', 0)))
                ]
            
            # Sprawdź czy marker o podanych współrzędnych istnieje
            marker_exists = any(
                abs(marker['lat'] - lat) < 0.0001 and abs(marker['lon'] - lon) < 0.0001 
                for marker in filtered_markers
            )
            
            return jsonify({'exists': marker_exists})

        @self.app.route('/update_user_location', methods=['POST'])
        def update_user_location():
            """Updates user location without changing navigation target"""
            data = request.json
            user_lat = data.get('user_lat')
            user_lon = data.get('user_lon')
            
            # Get or create user session
            user_id = session.get('user_id')
            if not user_id:
                user_id = str(uuid.uuid4())
                session['user_id'] = user_id
            
            user_data = session.get(user_id, {})
            
            # Update the user's marker without affecting other data
            user_marker = {
                "lat": user_lat,
                "lon": user_lon,
                "name": "User Location",
                "description": "This is your location"
            }
            user_data["marker"] = user_marker
            session[user_id] = user_data
            
            # Check if we have a selected target
            selected_target = user_data.get('selected_target')
            if selected_target:
                # Sprawdź czy użytkownik i cel są w województwie opolskim
                if not isInOpoleProvince(user_lat, user_lon):
                    user_data['current_route'] = None
                    session[user_id] = user_data
                    return jsonify({'status': 'success', 'message': 'User outside Opole province'})
                    
                if not isInOpoleProvince(selected_target['lat'], selected_target['lon']):
                    user_data['current_route'] = None
                    session[user_id] = user_data
                    return jsonify({'status': 'success', 'message': 'Target outside Opole province'})
                
                # Recalculate route only when both user and target are within Opole province
                route = get_route(
                    user_lat, user_lon,
                    selected_target['lat'], selected_target['lon']
                )
                if route:
                    self.add_route_to_map(route)
                    
                    # Get duration and distance from route
                    distance = route['routes'][0]['distance']  # in meters
                    duration = route['routes'][0]['duration'] / 60  # in minutes
                    distance_text = format_distance_text(distance)
                    
                    # Get target marker name
                    target_marker = next((marker for marker in self.markers 
                                 if abs(marker['lat'] - selected_target['lat']) < 0.0001
                                 and abs(marker['lon'] - selected_target['lon']) < 0.0001), None)
                    target_name = target_marker['name'] if target_marker else 'Unknown'
                    
                    return jsonify({
                        'status': 'success',
                        'distance': distance_text,
                        'duration': f"{duration:.0f}",
                        'name': target_name
                    })
            else:
                self.update_map()
            
            return jsonify({'status': 'success'})

        @self.app.route('/admin', methods=['GET'])
        def admin_dashboard():
            """Admin dashboard to manage toilets"""
            # Check if user is logged in
            if not session.get('admin_logged_in'):
                return flask.redirect('/admin/login')
            
            # User is logged in, show admin dashboard
            return send_from_directory('static/html', 'admin.html')

        @self.app.route('/api/toilets', methods=['GET'])
        def get_all_toilets():
            """API endpoint to get all toilets as JSON"""
            # Simple authentication
            password = request.headers.get('X-Admin-Key')
            if password != os.environ.get('ADMIN_KEY'):
                return jsonify({"error": "Access denied"}), 403
            
            toilets = self.load_markers()
            return jsonify(toilets)

        @self.app.route('/api/toilets/<int:toilet_id>', methods=['DELETE'])
        def delete_toilet(toilet_id):
            """Delete a toilet by ID"""
            # Simple authentication
            password = request.headers.get('X-Admin-Key')
            if password != os.environ.get('ADMIN_KEY'):
                return jsonify({"error": "Access denied"}), 403
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        # First delete comments associated with the toilet
                        cursor.execute('DELETE FROM comments WHERE toilet_id = ?', (toilet_id,))
                        # Then delete the toilet
                        cursor.execute('DELETE FROM toilets WHERE id = ?', (toilet_id,))
                        conn.commit()
                        
                        # Reload markers after deletion
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/toilets/<int:toilet_id>', methods=['PUT'])
        def update_toilet(toilet_id):
            """Update toilet data"""
            # Simple authentication
            password = request.headers.get('X-Admin-Key')
            if password != os.environ.get('ADMIN_KEY'):
                return jsonify({"error": "Access denied"}), 403
            
            data = request.json
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        cursor.execute('''
                        UPDATE toilets SET 
                            name = ?, 
                            description = ?, 
                            payable = ?,
                            onlyForClients = ?,
                            forDisabled = ?,
                            rating = ?,
                            base_rating = ?
                        WHERE id = ?
                        ''', (
                            data.get('name', ''),
                            data.get('description', ''),
                            1 if data.get('payable', False) else 0,
                            1 if data.get('onlyForClients', False) else 0,
                            1 if data.get('forDisabled', False) else 0,
                            self.safe_float(data.get('rating', 0)),
                            self.safe_float(data.get('base_rating', 0)),
                            toilet_id
                        ))
                        conn.commit()
                        
                        # Reload markers after update
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/comments/<int:comment_id>', methods =['PUT'])
        def update_comment(comment_id):
            """Update a comment by ID"""
            # Simple authentication
            password = request.headers.get('X-Admin-Key')
            if password != os.environ.get('ADMIN_KEY'):
                return jsonify({"error": "Access denied"}), 403
            
            data = request.json
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        cursor.execute('''
                        UPDATE comments SET comment = ?, rating = ?
                        WHERE id = ?
                        ''', (
                            data.get('comment', ''),
                            self.safe_float(data.get('rating', 0)),
                            comment_id
                        ))
                        conn.commit()
                        
                        # Update associated toilet's rating
                        cursor.execute('SELECT toilet_id FROM comments WHERE id = ?', (comment_id,))
                        result = cursor.fetchone()
                        if result:
                            toilet_id = result[0]
                            self.update_toilet_rating(toilet_id, cursor)
                            conn.commit()
                        
                        # Reload markers
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
        def delete_comment(comment_id):
            """Delete a comment by ID"""
            # Authentication and implementation similar to update_comment

        @self.app.route('/admin/login', methods=['GET', 'POST'])
        def admin_login():
            """Handle admin login"""
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                # Check against environment variables
                if username == os.environ.get('ADMIN_USER') and password == os.environ.get('ADMIN_PASSWORD'):
                    # Set session variable to mark user as logged in
                    session['admin_logged_in'] = True
                    # Redirect to admin dashboard
                    return flask.redirect('/admin')
                else:
                    # Przekieruj z komunikatem błędu jako parametrem URL
                    return flask.redirect('/admin/login?error=Invalid+username+or+password')
            
            # Dla żądań GET po prostu serwuj statyczny plik HTML
            return send_from_directory('static/html', 'login.html')

        @self.app.route('/admin/logout')
        def admin_logout():
            """Handle admin logout"""
            # Remove admin_logged_in from session
            session.pop('admin_logged_in', None)
            return flask.redirect('/admin/login')

        @self.app.route('/api/toilets/by-name/<string:name>', methods=['PUT'])
        def update_toilet_by_name(name):
            """Update a toilet by name"""
            if not session.get('admin_logged_in'):
                return jsonify({"error": "Access denied"}), 403
            
            data = request.json
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        # Find the toilet by name
                        cursor.execute('SELECT id FROM toilets WHERE name = ?', (name,))
                        result = cursor.fetchone()
                        if not result:
                            return jsonify({"error": "Toilet not found"}), 404
                        
                        toilet_id = result[0]
                        
                        # Update the toilet
                        cursor.execute('''
                        UPDATE toilets SET 
                            name = ?, 
                            description = ?, 
                            payable = ?,
                            onlyForClients = ?,
                            forDisabled = ?,
                            rating = ?,
                            base_rating = ?
                        WHERE id = ?
                        ''', (
                            data.get('name', ''),
                            data.get('description', ''),
                            1 if data.get('payable', False) else 0,
                            1 if data.get('onlyForClients', False) else 0,
                            1 if data.get('forDisabled', False) else 0,
                            self.safe_float(data.get('rating', 0)),
                            self.safe_float(data.get('base_rating', 0)),
                            toilet_id
                        ))
                        conn.commit()
                        
                        # Reload markers
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/toilets/by-name/<string:name>', methods=['DELETE'])
        def delete_toilet_by_name(name):
            """Delete a toilet by name"""
            if not session.get('admin_logged_in'):
                return jsonify({"error": "Access denied"}), 403
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        # Find the toilet by name
                        cursor.execute('SELECT id FROM toilets WHERE name = ?', (name,))
                        result = cursor.fetchone()
                        if not result:
                            return jsonify({"error": "Toilet not found"}), 404
                        
                        toilet_id = result[0]
                        
                        # Delete comments first
                        cursor.execute('DELETE FROM comments WHERE toilet_id = ?', (toilet_id,))
                        # Then delete the toilet
                        cursor.execute('DELETE FROM toilets WHERE id = ?', (toilet_id,))
                        conn.commit()
                        
                        # Reload markers
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/add_comment', methods=['POST'])
        def admin_add_comment():
            """Admin endpoint to add a comment to a toilet"""
            if not session.get('admin_logged_in'):
                return jsonify({"error": "Access denied"}), 403
            
            toilet_id = request.form.get('toilet_id')
            comment_text = request.form.get('comment')
            rating = request.form.get('rating')
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        # Add comment
                        cursor.execute(
                            'INSERT INTO comments (toilet_id, comment, rating) VALUES (?, ?, ?)',
                            (toilet_id, comment_text, rating)
                        )
                        
                        # Update toilet rating
                        cursor.execute(
                            'SELECT AVG(rating) FROM comments WHERE toilet_id = ?',
                            (toilet_id,)
                        )
                        avg_comment_rating = cursor.fetchone()[0] or 0
                        
                        cursor.execute(
                            'SELECT base_rating FROM toilets WHERE id = ?',
                            (toilet_id,)
                        )
                        base_rating = cursor.fetchone()[0] or 0
                        
                        cursor.execute(
                            'SELECT COUNT(*) FROM comments WHERE toilet_id = ?',
                            (toilet_id,)
                        )
                        comment_count = cursor.fetchone()[0]
                        
                        # Calculate new rating
                        computed_rating = (float(base_rating) + float(avg_comment_rating) * comment_count) / (1 + comment_count)
                        
                        # Update toilet rating
                        cursor.execute(
                            'UPDATE toilets SET rating = ? WHERE id = ?',
                            (computed_rating, toilet_id)
                        )
                        
                        conn.commit()
                        
                        # Reload markers after update
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/delete_comment', methods=['POST'])
        def admin_delete_comment():
            """Delete a comment by toilet_id and comment index"""
            if not session.get('admin_logged_in'):
                return jsonify({"error": "Access denied"}), 403
            
            data = request.json
            toilet_id = data.get('toilet_id')
            comment_index = data.get('comment_index')
            
            try:
                # Bezpieczna konwersja comment_index na liczbę całkowitą
                try:
                    comment_index = int(comment_index)
                except (ValueError, TypeError):
                    return jsonify({"error": "Invalid comment index"}), 400
                    
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    conn.row_factory = sqlite3.Row
                    with closing(conn.cursor()) as cursor:
                        # Get all comments for this toilet
                        cursor.execute(
                            'SELECT id FROM comments WHERE toilet_id = ? ORDER BY created_at',
                            (toilet_id,)
                        )
                        comments = cursor.fetchall()
                        
                        if comment_index >= len(comments):
                            return jsonify({"error": "Comment not found"}), 404
                        
                        # Get the comment ID to delete
                        comment_id = comments[int(comment_index)]['id']
                        
                        # Delete the comment
                        cursor.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
                        
                        # Update the toilet's rating
                        cursor.execute(
                            'SELECT AVG(rating) FROM comments WHERE toilet_id = ?',
                            (toilet_id,)
                        )
                        avg_comment_rating = cursor.fetchone()[0] or 0
                        
                        cursor.execute(
                            'SELECT base_rating FROM toilets WHERE id = ?',
                            (toilet_id,)
                        )
                        base_rating = cursor.fetchone()[0] or 0
                        
                        cursor.execute(
                            'SELECT COUNT(*) FROM comments WHERE toilet_id = ?',
                            (toilet_id,)
                        )
                        comment_count = cursor.fetchone()[0]
                        
                        # Calculate new rating
                        if comment_count > 0:
                            computed_rating = (float(base_rating) + float(avg_comment_rating) * comment_count) / (1 + comment_count)
                        else:
                            computed_rating = float(base_rating)
                        
                        # Update toilet rating
                        cursor.execute(
                            'UPDATE toilets SET rating = ? WHERE id = ?',
                            (computed_rating, toilet_id)
                        )
                        
                        conn.commit()
                        
                        # Reload markers after update
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

    def add_marker_to_map(self, marker):
        """
        Dodaje POJEDYNCZY marker do mapy self.m.
        """

        try:
            if self.m is None:
                self.m = self.create_map()

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
                        <p>{marker.get('description','')}</p>
                    </div>
                """
                folium.Marker(
                    location=[marker['lat'], marker['lon']],
                    popup=popup_content,
                    icon=icon
                ).add_to(self.m)
            else:
                # Get user location from session
                user_id = session.get('user_id')
                user_data = session.get(user_id, {}) if user_id else {}
                user_marker = user_data.get('marker')
                
                # Calculate distance if user location exists
                distance_km = None
                is_within_range = False
                # If user_marker exists, calculate the distance
                if user_marker:
                    distance = haversine(
                        user_marker['lat'], user_marker['lon'],
                        marker['lat'], marker['lon']
                    )
                    distance_km = distance / 1000  # Convert distance to kilometers
                    is_within_range = distance_km <= 10
                else:
                    is_within_range = False

                # Create toilet marker with modified navigation button
                lat = marker['lat']
                lon = marker['lon']

                onclick_attr = f"window.parent.navigateToToilet({lat}, {lon})"
                disabled_attr = "" if is_within_range else 'disabled="disabled"'

                navigate_button_html = f"""
                    <button onclick="{onclick_attr}"
                            class="popup-button" 
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
                            onmouseover="this.style.backgroundColor='#C92704';this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)'"
                            onmouseout="this.style.backgroundColor='red';this.style.transform='none';this.style.boxShadow='none'"
                            {disabled_attr}>
                        Nawiguj
                    </button>
                    {f'<span style="color: #d32f2f; font-size: 12px; margin-left: 8px;">Toaleta znajduje się dalej niż 10km</span>' if not is_within_range else ''}
                """

                # Marker toalety (globalny)
                iconToilet = folium.CustomIcon(
                    toilet_icon, 
                    icon_size=(50, 50), 
                    shadow_size=(50, 50)
                )
                name = marker.get('name', 'Unknown')
                description = marker.get('description', 'No description')
                payable = "TAK" if marker.get('payable', False) else "NIE"
                onlyForClients = "TAK" if marker.get('onlyForClients', False) else "NIE"
                forDisabled = "TAK" if marker.get('forDisabled', False) else "NIE"
                try:
                    base_rating = float(marker.get('base_rating', marker.get('rating', 0)))
                except ValueError:
                    base_rating = 0

                comment_list = marker.get('comments', [])
                comment_ratings = []
                for c in comment_list:
                    try:
                        comment_ratings.append(float(c.get('rating', 0)))
                    except ValueError:
                        pass

                if comment_ratings:
                    computed_rating = (base_rating + sum(comment_ratings)) / (1 + len(comment_ratings))
                    rating_display = f"{computed_rating:.1f}"
                elif base_rating:
                    rating_display = f"{base_rating:.1f}"
                else:
                    rating_display = "Brak oceny"
                photo_base64 = marker.get('photo', None)
                comments_list = marker.get('comments', [])
                photo_html = ""
                if photo_base64:
                    photo_html = f"""
                        <img src="data:image/jpeg;base64,{photo_base64}" 
                            style="max-width: 150px; max-height: 150px; width: auto; height: auto; 
                                    object-fit: contain; border-radius: 4px; display: block; margin: 10px 0;">
                    """

                # Sekcja komentarzy
                comments_html = f"""
                    <div id='comments-container-{marker["lat"]}-{marker["lon"]}'>
                        <div id='comments-{marker["lat"]}-{marker["lon"]}'
                            style='max-height: 80px; overflow-y: hidden; font-family: Roboto, sans-serif; 
                                    scrollbar-width: thin; scrollbar-color: #888 #f1f1f1; padding-right: 5px;
                                    -webkit-scrollbar-width: thin; -webkit-scrollbar-color: #888 #f1f1f1;'>
                            <style>
                                #comments-{marker["lat"]}-{marker["lon"]}::-webkit-scrollbar {{
                                    width: 8px;
                                }}
                                #comments-{marker["lat"]}-{marker["lon"]}::-webkit-scrollbar-track {{
                                    background: #f1f1f1;
                                    border-radius: 4px;
                                }}
                                #comments-{marker["lat"]}-{marker["lon"]}::-webkit-scrollbar-thumb {{
                                    background: #888;
                                    border-radius: 4px;
                                }}
                                #comments-{marker["lat"]}-{marker["lon"]}::-webkit-scrollbar-thumb:hover {{
                                    background: #555;
                                }}
                            </style>
                """
                
                # Pokazujemy tylko pierwszy komentarz domyślnie
                if comments_list:
                    first_comment = comments_list[0]
                    comments_html += f"""
                        <p><strong>Ocena:</strong> {first_comment.get('rating')}</p>
                        <p>{first_comment.get('comment')}</p>
                    """

                    # Pozostałe komentarze 
                    if len(comments_list) > 1:
                        for c in comments_list[1:]:
                            comments_html += f"""
                            <hr style="border-top: 1px solid #ccc;" />
                            <p><strong>Ocena:</strong> {c.get('rating')}</p>
                            <p>{c.get('comment')}</p>
                            """

                comments_html += "</div>"

                if len(comments_list) > 1:
                    comments_html += f"""
                        <button onclick="
                            var commentsDiv = document.getElementById('comments-{marker["lat"]}-{marker["lon"]}');
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

                # Użycie współrzędnych jako identyfikatora
                comment_button_html = f"""
                    <button onclick="window.parent.openCommentModal({lat}, {lon})" 
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
                            onmouseover="this.style.backgroundColor='#C92704';this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)'"
                            onmouseout="this.style.backgroundColor='red';this.style.transform='none';this.style.boxShadow='none'"
                    >
                        Dodaj komentarz
                    </button>
                """
                # Check if toilet is currently open
                is_open, status_text = self.is_toilet_open(marker)
                status_class = "status-open" if is_open else "status-closed"
                
                # Display opening hours status
                opening_hours_html = f"""
                    <p><strong>Status:</strong> <span class="{status_class}">{status_text}</span></p>
                """
                
                # Add opening hours details
                opening_hours = marker.get('openingHours', {})
                if opening_hours.get('is24h', False):
                    opening_hours_html += "<p><strong>Godziny otwarcia:</strong> Czynne całą dobę</p>"
                else:
                    schedule = opening_hours.get('schedule', {})
                    if schedule:
                        opening_hours_html += "<details><summary><strong>Godziny otwarcia</strong></summary><div style='margin-top: 5px;'>"
                        day_names = {
                            'monday': 'Poniedziałek',
                            'tuesday': 'Wtorek',
                            'wednesday': 'Środa',
                            'thursday': 'Czwartek',
                            'friday': 'Piątek',
                            'saturday': 'Sobota',
                            'sunday': 'Niedziela'
                        }
                        
                        for day_key, day_name in day_names.items():
                            day_schedule = schedule.get(day_key)
                            if day_schedule:
                                opening_hours_html += f"<p>{day_name}: {day_schedule['open']} - {day_schedule['close']}</p>"
                            else:
                                opening_hours_html += f"<p>{day_name}: Zamknięte</p>"
                        
                        opening_hours_html += "</div></details>"
                    else:
                        opening_hours_html += "<p><strong>Godziny otwarcia:</strong> Brak danych</p>"

                if not comments_list:
                    wholePopUp = f"""
                        <div style="width: 300px; max-height:300px, overflow-y: auto;">
                            <h2>{name}</h2>
                            <p>{description}</p>
                            <p><strong>Płatna:</strong> {payable}</p>
                            <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                            <p><strong>Dla niepełnosprawnych:</strong>{forDisabled}</p>
                            {opening_hours_html}
                            <p><strong>Ocena:</strong> {rating_display}</p>
                            <div style="display: flex; flex-wrap: wrap; gap: 5px; justify-content: center;">
                                {photo_html}
                            </div>
                            {comments_html}
                            {navigate_button_html}
                            {comment_button_html}
                        </div>
                    """
                else:
                    wholePopUp = f"""
                        <div style="width: 300px; max-height:300px, overflow-y: auto;">
                            <h2>{name}</h2>
                            <p>{description}</p>
                            <p><strong>Płatna:</strong> {payable}</p>
                            <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                            <p><strong>Dla niepełnosprawnych:</strong>{forDisabled}</p>
                            {opening_hours_html}
                            <p><strong>Ocena:</strong> {rating_display}</p>
                            <div style="display: flex; flex-wrap: wrap; gap: 5px; justify-content: center;">
                                {photo_html}
                            </div>
                            <h3 style='margin-top: 0;'>Komentarze</h3>
                            {comments_html}
                            {navigate_button_html}
                            {comment_button_html}
                        </div>
                    """
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(
                        wholePopUp,
                        min_width=250,  # Set minimum width in pixels
                        max_height=300  # Set maximum height in pixels
                    ),
                    icon=iconToilet
                ).add_to(self.m)
                self.save_markers()
        except AttributeError as e:
            logging.error(f"Błąd podczas dodawania markera: {e}")
            # Spróbuj odtworzyć mapę
            self.m = self.create_map()
            # Rekurencyjnie spróbuj dodać marker ponownie
            self.add_marker_to_map(marker)
        except Exception as e:
            logging.error(f"Nieoczekiwany błąd podczas dodawania markera: {e}")
            # Można dodać dodatkową obsługę innych wyjątków
        
    def safe_float(self, value, default=0):
        """Safely convert a value to float, returning default if conversion fails."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def add_route_to_map(self, route):
        """
        Zapisuje JEDNĄ trasę (current_route) w sesji aktualnego użytkownika
        i (opcjonalnie) od razu wywołuje update_map().
        """
        user_id = session.get('user_id')
        if not user_id:
            logging.warning("Brak user_id w sesji – nie można zapisać trasy.")
            return

        user_data = session.get(user_id, {})
        user_data['current_route'] = route
        session[user_id] = user_data

        # Opcjonalnie można odświeżyć mapę już teraz
        self.update_map()

    def update_map(self):
        """Aktualizuje mapę, najpierw ją usuwając"""
        try:
            # Wyczyść starą mapę
            if hasattr(self, 'm') and self.m is not None:
                del self.m
                self.m = None
                
            # Ustaw centrum mapy
            user_id = session.get('user_id')
            center_lat = self.default_lat
            center_lon = self.default_lon
            
            if user_id:
                user_data = session.get(user_id, {})
                user_marker = user_data.get('marker')
                if user_marker:
                    center_lat = user_marker['lat']
                    center_lon = user_marker['lon']

            # Utwórz nową mapę
            self.m = self.create_map(center_lat, center_lon)

            # Dodaj markery i trasy
            # Dodajemy globalne markery (toalety)
            markers_to_add = self.markers
            if user_id:
                user_data = session.get(user_id, {})
                filters = user_data.get('filters', {})
                filter_payable = filters.get('filterPayable', False)
                filter_for_clients = filters.get('filterForClients', False)
                filter_for_disabled = filters.get('filterForDisabled', False)
                filter_rating = float(filters.get('filterRating', 0))

                if filter_payable or filter_for_clients or filter_for_disabled or filter_rating > 0:
                    markers_to_add = [
                        marker for marker in self.original_markers
                        if (not filter_payable or marker.get('payable', False)) and
                           (not filter_for_clients or marker.get('onlyForClients', False)) and
                           (not filter_for_disabled or marker.get('forDisabled', False)) and
                           (float(marker.get('rating', 0)) >= filter_rating)
                    ]

            for marker in markers_to_add:
                self.add_marker_to_map(marker)

            # Dodajemy marker + trasę użytkownika
            if user_id:
                user_data = session.get(user_id, {})
                user_marker = user_data.get('marker')
                if user_marker:
                    self.add_marker_to_map(user_marker)

                    # Filtrujemy by nie brać pod uwagę markera użytkownika
                    filtered_markers = [
                        marker for marker in markers_to_add 
                        if marker.get('name', '') != "User Location"
                    ]
                    # Sprawdź czy zapisany cel nawigacji nadal istnieje po filtrowaniu
                    selected_target = user_data.get('selected_target')
                    if selected_target:
                        target_lat = selected_target.get('lat')
                        target_lon = selected_target.get('lon')
                        
                        # Sprawdź czy cel nawigacji nadal istnieje w przefiltrowanych markerach
                        target_exists = any(
                            abs(marker['lat'] - target_lat) < 0.0001 and abs(marker['lon'] - target_lon) < 0.0001
                            for marker in filtered_markers
                        )

                        if not target_exists:
                            # Cel nawigacji nie istnieje po filtrowaniu, usuwamy trasę i cel
                            user_data['current_route'] = None
                            user_data['selected_target'] = None
                            session[user_id] = user_data
            
                    if not filtered_markers:
                        user_data['current_route'] = None
                        session[user_id] = user_data
                    else:
                        # Dodaj sprawdzenie dla lokalizacji użytkownika
                        if user_marker and not isInOpoleProvince(user_marker['lat'], user_marker['lon']):
                            logging.warning("Użytkownik poza województwem opolskim - nie generuję trasy.")
                            user_data['current_route'] = None
                            session[user_id] = user_data
                        else:
                            # Używamy trasy zapisanej w sesji, jeśli istnieje
                            route = user_data.get('current_route')
                            
                            # Sprawdź czy cel nawigacji jest w województwie opolskim
                            selected_target = user_data.get('selected_target')
                            if selected_target and not isInOpoleProvince(selected_target['lat'], selected_target['lon']):
                                logging.warning("Cel nawigacji poza województwem opolskim - usuwam trasę.")
                                user_data['current_route'] = None
                                route = None
                                session[user_id] = user_data
                            
                            if not route:
                                # Reszta kodu bez zmian...
                                route = None
                                nearest_marker = find_nearest_marker(user_marker, filtered_markers)
                                if nearest_marker:
                                    # Sprawdzamy województwo przed jakimkolwiek generowaniem trasy
                                    if not isInOpoleProvince(nearest_marker['lat'], nearest_marker['lon']):
                                        logging.warning("Marker poza województwem opolskim – nie generuję trasy.")
                                        user_data['current_route'] = None
                                        session[user_id] = user_data
                                    else:
                                        route = get_route(
                                            user_marker['lat'], user_marker['lon'],
                                            nearest_marker['lat'], nearest_marker['lon']
                                        )
                                        if route:
                                            user_data['current_route'] = route
                                            session[user_id] = user_data

                        # Wyświetlamy trasę tylko jeśli route istnieje i marker jest w województwie
                        if route:
                            coordinates = [
                                (coord[1], coord[0])
                                for coord in route['routes'][0]['geometry']['coordinates']
                            ]
                            distance = route['routes'][0]['distance']  # w metrach
                            distance_text = f"{distance / 1000:.2f} km"

                            folium.PolyLine(
                                locations=coordinates,
                                color='#d00000',
                                weight=5,
                                opacity=0.7
                            ).add_to(self.m)

                            mid_point_index = len(coordinates) // 2
                            mid_point = coordinates[mid_point_index]
                            offset_latitude = 0.0007
                            offset_longitude = 0.0007
                            mid_point_with_offset = [mid_point[0] + offset_latitude, mid_point[1] + offset_longitude]

                            folium.Marker(
                                location=mid_point_with_offset,
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
                                            font-family: Arial, sans-serif;
                                            box-shadow: 0 0.15em 0.3em rgba(0,0,0,0.1);
                                            display: inline-block;
                                            min-width: max-content;
                                            white-space: nowrap;
                                        ">
                                            {distance_text}
                                        </div>
                                    """
                                )
                            ).add_to(self.m)

            return self.m._repr_html_()
        except Exception as e:
            logging.error(f"Błąd podczas aktualizacji mapy: {e}")
            self.m = self.create_map()
            return self.m._repr_html_()

    def setup_database(self):
        """Initialize SQLite database and create tables if they don't exist"""
        with closing(sqlite3.connect('data/toilets.db')) as conn:
            with closing(conn.cursor()) as cursor:
                # Create toilets table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS toilets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    payable BOOLEAN NOT NULL DEFAULT 0,
                    onlyForClients BOOLEAN NOT NULL DEFAULT 0,
                    forDisabled BOOLEAN NOT NULL DEFAULT 0,
                    rating REAL DEFAULT 0,
                    base_rating REAL DEFAULT 0,
                    photo TEXT
                )
                ''')
                
                # Create comments table with foreign key to toilets
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    toilet_id INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    rating REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (toilet_id) REFERENCES toilets (id) ON DELETE CASCADE
                )
                ''')
                conn.commit()

    def runThePage(self):
        self.app.run(host = os.environ.get('SERVER_HOST'), port=os.environ.get('SERVER_PORT'))

    def is_toilet_open(self, marker):
        """Checks if a toilet is currently open based on its opening hours."""
        try:
            # Get current day and time
            now = datetime.datetime.now()
            current_day = now.strftime('%A').lower()  # Get day name in lowercase
            current_time = now.strftime('%H:%M')  # Get time in HH:MM format
            
            # Map English day names to our keys
            day_map = {
                'monday': 'monday',
                'tuesday': 'tuesday',
                'wednesday': 'wednesday',
                'thursday': 'thursday',
                'friday': 'friday',
                'saturday': 'saturday',
                'sunday': 'sunday'
            }
            
            # Get opening hours
            opening_hours = marker.get('openingHours', {})
            
            # If it's open 24/7
            if opening_hours.get('is24h', False):
                return True, "Otwarte 24/7"
                
            # Get schedule for current day
            day_key = day_map.get(current_day)
            if not day_key:
                return False, "Brak danych o godzinach"
                
            schedule = opening_hours.get('schedule', {})
            day_schedule = schedule.get(day_key)
            
            # If no schedule for today, assume it's closed
            if not day_schedule:
                return False, "Dzisiaj zamknięte"
                
            open_time = day_schedule.get('open')
            close_time = day_schedule.get('close')
            
            # If missing opening or closing time, assume it's closed
            if not open_time or not close_time:
                return False, "Brak danych o godzinach"
                
            # Check if current time is between open and close times
            is_open = open_time <= current_time <= close_time
            
            if is_open:
                return True, f"Otwarte (do {close_time})"
            else:
                if current_time < open_time:
                    return False, f"Zamknięte (otwarcie o {open_time})"
                else:
                    return False, "Zamknięte"
                    
        except Exception as e:
            logging.error(f"Error checking if toilet is open: {e}")
            return False, "Brak danych o godzinach"

    def allowed_file(self, filename):
        """Check if uploaded file has an allowed extension"""
        if not filename:
            return False
            
        # Define allowed extensions for image uploads
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
        
        # Check if the file has a '.' and the extension is in allowed extensions
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
