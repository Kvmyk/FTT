import os
import folium
import flask
import uuid
import logging
import threading
import time
import sqlite3
import datetime
import gc
import gunicorn
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
        self.default_lat = 50.6751
        self.default_lon = 17.9213

        # Setup database
        self.setup_database()
        
        # Ładujemy globalne markery z bazy danych (toalety)
        self.markers = self.load_markers()
        self.original_markers = self.markers.copy()  # Przechowujemy oryginalną listę markerów

        # Inicjalizacja mapy jako None
        self.m = None

        self.setup_routes()
        self.setup_database()

        # Upewnij się, że katalog na zdjęcia istnieje
        self.uploads_dir = os.path.join('static', 'uploads')
        if not os.path.exists(self.uploads_dir):
            os.makedirs(self.uploads_dir)
    
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
            gc.collect()  # Force garbage collection
            
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
            with closing(sqlite3.connect('data/toilets.db')) as conn:
                conn.row_factory = sqlite3.Row
                with closing(conn.cursor()) as cursor:
                    markers = []
                    
                    # Query all toilets
                    cursor.execute('SELECT * FROM toilets')
                    toilets = cursor.fetchall()
                    
                    for toilet in toilets:
                        # Convert SQLite Row to dict
                        marker = dict(toilet)
                        
                        # Convert boolean integers to Python booleans
                        marker['payable'] = bool(marker['payable'])
                        marker['onlyForClients'] = bool(marker['onlyForClients'])
                        marker['forDisabled'] = bool(marker['forDisabled'])
                        
                        # Add opening hours to the marker
                        marker['weekday_open'] = toilet['weekday_open']
                        marker['weekday_close'] = toilet['weekday_close']
                        marker['weekend_open'] = toilet['weekend_open']
                        marker['weekend_close'] = toilet['weekend_close']
                        
                        # Get comments for this toilet
                        cursor.execute('SELECT comment, rating FROM comments WHERE toilet_id = ?', 
                                      (toilet['id'],))
                        comments = [dict(c) for c in cursor.fetchall()]
                        if comments:
                            marker['comments'] = comments
                        
                        markers.append(marker)
                    
                    return markers
        except sqlite3.Error as e:
            logging.error(f"SQLite error loading markers: {e}")
            return []

    def save_markers(self):
        """Save markers to SQLite database."""
        try:
            with closing(sqlite3.connect('data/toilets.db')) as conn:
                with closing(conn.cursor()) as cursor:
                    # For simplicity, we're recreating all data
                    cursor.execute('DELETE FROM comments')
                    cursor.execute('DELETE FROM toilets')
                    
                    for marker in self.original_markers:
                        # Insert toilet record with opening hours
                        cursor.execute('''
                        INSERT INTO toilets (lat, lon, name, place_name, description, payable, 
                                            onlyForClients, forDisabled, rating, 
                                            base_rating, weekday_open, weekday_close,
                                            weekend_open, weekend_close, photo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            marker['lat'],
                            marker['lon'],
                            marker.get('name', 'Unknown'),
                            marker.get('place_name', ''),
                            marker.get('description', ''),
                            1 if marker.get('payable', False) else 0,
                            1 if marker.get('onlyForClients', False) else 0,
                            1 if marker.get('forDisabled', False) else 0,
                            self.safe_float(marker.get('rating', 0)),
                            self.safe_float(marker.get('base_rating', 0)),
                            marker.get('weekday_open', ''),
                            marker.get('weekday_close', ''),
                            marker.get('weekend_open', ''),
                            marker.get('weekend_close', ''),
                            marker.get('photo', None)
                        ))
                        
                        toilet_id = cursor.lastrowid
                        
                        # Insert comments if any
                        for comment in marker.get('comments', []):
                            cursor.execute('''
                            INSERT INTO comments (toilet_id, comment, rating)
                            VALUES (?, ?, ?)
                            ''', (
                                toilet_id,
                                comment.get('comment', ''),
                                self.safe_float(comment.get('rating', 0))
                            ))
                    
                    conn.commit()
        except sqlite3.Error as e:
            logging.error(f"SQLite error saving markers: {e}")

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
            data = request.form
            userInput = data.get('userInput', '')
            place_name = data.get('place_name', '')  # Get place name from form
            description = data.get('description', '')
            payable = data.get('payable', 'false').lower() == 'true'
            onlyForClients = data.get('onlyForClients', 'false').lower() == 'true'
            forDisabled = data.get('forDisabled', 'false').lower() == 'true'
            rating = data.get('rating', '0')
            useUserLocation = data.get('useUserLocation', 'false').lower() == 'true'
            
            # Get opening hours
            weekday_open = data.get('weekdayOpenTime', '')
            weekday_close = data.get('weekdayCloseTime', '')
            weekend_open = data.get('weekendOpenTime', '')
            weekend_close = data.get('weekendCloseTime', '')
            
            photo = request.files.get('photos')  # może być None
            photo_path = None
            if photo:
                # Generuj unikalną nazwę pliku z rozszerzeniem
                file_ext = os.path.splitext(photo.filename)[1] if photo.filename else '.jpg'
                photo_filename = f"{uuid.uuid4()}{file_ext}"
                
                # Poprawnie definiuj ścieżki
                photo_path = os.path.join('uploads', photo_filename)  # Względna ścieżka dla HTML/DB
                full_path = os.path.join('static', photo_path)  # Pełna ścieżka do zapisu pliku
                
                # Zapisz plik
                photo.save(full_path)

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

            existing_marker = next((m for m in self.markers if m['lat'] == lat and m['lon'] == lon), None)
            if existing_marker:
                # Add place_name to existing marker if provided
                if place_name:
                    existing_marker['place_name'] = place_name
                existing_marker.setdefault('comments', []).append({
                    'comment': description,
                    'rating': rating
                })
                if 'base_rating' not in existing_marker:
                    existing_marker['base_rating'] = existing_marker.get('rating', rating)
                try:
                    base_rating = float(existing_marker.get('base_rating', 0))
                except ValueError:
                    base_rating = 0
                comment_ratings = []
                for c in existing_marker.get('comments', []):
                    try:
                        comment_ratings.append(float(c.get('rating', 0)))
                    except ValueError:
                        pass
                computed_rating = (base_rating + sum(comment_ratings)) / (1 + len(comment_ratings))
                existing_marker['rating'] = f"{computed_rating:.1f}"
            else:
                new_marker = {
                    "lat": lat,
                    "lon": lon,
                    "name": userInput,
                    "place_name": place_name,  # Add place_name to new marker
                    "description": description,
                    "payable": payable,
                    "onlyForClients": onlyForClients,
                    "rating": rating,
                    "base_rating": rating,  # Dodaj tę linię, by base_rating było takie samo jak rating
                    "photo": photo_path,  # Ścieżka zamiast base64
                    "forDisabled": forDisabled,
                    'weekday_open': data.get('weekday_open', ''),
                    'weekday_close': data.get('weekday_close', ''),
                    'weekend_open': data.get('weekend_open', ''),
                    'weekend_close': data.get('weekend_close', '')
                }
                self.markers.append(new_marker)
                self.original_markers.append(new_marker)
            self.save_markers()

            user_id = session.get('user_id')
            if user_id:
                user_data = session.get(user_id, {})
                filters = user_data.get('filters', {})
                filter_payable = filters.get('filterPayable', False)
                filter_for_clients = filters.get('filterForClients', False)
                filter_for_disabled = filters.get('filterForDisabled', False)
                filter_rating = float(filters.get('filterRating', 0))
                markers_to_search = self.original_markers
                if filter_payable or filter_for_clients or filter_for_disabled or filter_rating > 0:
                    markers_to_search = [
                        marker for marker in self.original_markers
                        if (not filter_payable or marker.get('payable', False)) and
                           (not filter_for_clients or marker.get('onlyForClients', False)) and
                           (not filter_for_disabled or marker.get('forDisabled', False)) and
                           (float(marker.get('rating', 0)) >= filter_rating)
                    ]
                user_marker = user_data.get('marker')
                if user_marker:
                    filtered_markers = [
                        marker for marker in markers_to_search 
                        if marker.get('name', '') != "User Location"
                    ]
                    if filtered_markers:
                        nearest_marker = find_nearest_marker(user_marker, filtered_markers)
                        if nearest_marker:
                            route = get_route(
                                user_marker['lat'], user_marker['lon'],
                                nearest_marker['lat'], nearest_marker['lon']
                            )
                            if route:
                                self.add_route_to_map(route)
            self.update_map()
            return jsonify({'status': 'success'})

        @self.app.after_request
        def add_header(response):
            """
            Wyłączamy cache, by mieć pewność że mapy/markery nie są trzymane w pamięci przeglądarki.
            """
            response.headers['Cache-Control'] = 'no-store'
            return response

        @self.app.route('/render_map', methods=['GET'])
        def render_map():
            """
            Endpoint, który zwraca HTML (mapę z poliliniami i markerami)
            do wstawienia w <div id="map"> w pliku HTML.
            """
            return self.update_map()

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
                        self.clean_orphaned_photos()
                        
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
                            place_name = ?,
                            description = ?, 
                            payable = ?,
                            onlyForClients = ?,
                            forDisabled = ?,
                            rating = ?,
                            base_rating = ?,
                            weekday_open = ?,
                            weekday_close = ?,
                            weekend_open = ?,
                            weekend_close = ?
                        WHERE id = ?
                        ''', (
                            data.get('name', ''),
                            data.get('place_name', ''),
                            data.get('description', ''),
                            1 if data.get('payable', False) else 0,
                            1 if data.get('onlyForClients', False) else 0,
                            1 if data.get('forDisabled', False) else 0,
                            self.safe_float(data.get('rating', 0)),
                            self.safe_float(data.get('base_rating', 0)),
                            data.get('weekday_open', ''),
                            data.get('weekday_close', ''),
                            data.get('weekend_open', ''),
                            data.get('weekend_close', ''),
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
                        self.clean_orphaned_photos()  # Dodaj tę linię
                        
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

        @self.app.route('/api/toilets/photo', methods=['DELETE'])
        def delete_toilet_photo():
            """Delete a toilet's photo"""
            if not session.get('admin_logged_in'):
                return jsonify({"error": "Access denied"}), 403
            
            toilet_id = request.json.get('toilet_id')
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        # Get the current photo path
                        cursor.execute('SELECT photo FROM toilets WHERE id = ?', (toilet_id,))
                        result = cursor.fetchone()
                        if not result or not result[0]:
                            return jsonify({"error": "Toilet has no photo"}), 404
                        
                        photo_path = result[0]
                        
                        # Update the database to remove the photo reference
                        cursor.execute('UPDATE toilets SET photo = NULL WHERE id = ?', (toilet_id,))
                        conn.commit()
                        
                        # Delete the physical file
                        full_path = os.path.join('static', photo_path)
                        if os.path.exists(full_path):
                            os.remove(full_path)
                        
                        # Reload markers
                        self.markers = self.load_markers()
                        self.original_markers = self.markers.copy()
                        
                        return jsonify({"success": True})
            except sqlite3.Error as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/toilets/bulk-delete', methods=['POST'])
        def bulk_delete_toilets():
            """Delete multiple toilets at once"""
            if not session.get('admin_logged_in'):
                return jsonify({"error": "Access denied"}), 403
            
            toilet_ids = request.json.get('toilet_ids', [])
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        for toilet_id in toilet_ids:
                            # Get the photo path before deleting
                            cursor.execute('SELECT photo FROM toilets WHERE id = ?', (toilet_id,))
                            result = cursor.fetchone()
                            if result and result[0]:
                                photo_path = result[0]
                                full_path = os.path.join('static', photo_path)
                                if os.path.exists(full_path):
                                    os.remove(full_path)
                            
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

        @self.app.route('/api/comments/bulk-delete', methods=['POST'])
        def bulk_delete_comments():
            """Delete multiple comments at once"""
            if not session.get('admin_logged_in'):
                return jsonify({"error": "Access denied"}), 403
            
            comment_ids = request.json.get('comment_ids', [])
            
            try:
                with closing(sqlite3.connect('data/toilets.db')) as conn:
                    with closing(conn.cursor()) as cursor:
                        # Get unique toilet IDs for all comments to update ratings later
                        toilet_ids = set()
                        for comment_id in comment_ids:
                            cursor.execute('SELECT toilet_id FROM comments WHERE id = ?', (comment_id,))
                            result = cursor.fetchone()
                            if result:
                                toilet_ids.add(result[0])
                        
                        # Delete the comments
                        for comment_id in comment_ids:
                            cursor.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
                        
                        # Update ratings for all affected toilets
                        for toilet_id in toilet_ids:
                            self.update_toilet_rating(toilet_id, cursor)
                        
                        conn.commit()
                        
                        # Reload markers
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
                    <button onclick="{onclick_attr}; this.closest('.leaflet-popup').style.display='none';"
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
                    icon_size=(75, 75), 
                    shadow_size=(50, 50)
                )
                name = marker.get('name', 'Unknown')
                place_name = marker.get('place_name', '')
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
                photo_path = marker.get('photo', None)
                comments_list = marker.get('comments', [])
                photo_html = ""
                if photo_path:
                    photo_html = f"""
                        <img src="/static/{photo_path}" 
                            style="max-width: 150px; max-height: 150px; width: auto; height: auto; 
                                    object-fit: contain; border-radius: 4px; display: block; margin: 10px 0;"
                            loading="lazy">
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
                # Get opening hours information
                weekday_open = marker.get('weekday_open', '')
                weekday_close = marker.get('weekday_close', '')
                weekend_open = marker.get('weekend_open', '')
                weekend_close = marker.get('weekend_close', '')

                # Check if the toilet is currently open
                is_open = False
                has_hours = False
                current_status = ""
                hours_info = ""

                if weekday_open and weekday_close or weekend_open and weekend_close:
                    has_hours = True
                    now = datetime.datetime.now()
                    current_day = now.weekday()  # 0-4 for weekdays, 5-6 for weekend
                    current_time = now.time()
                    
                    # Dodaj 1 godzinę do aktualnego czasu dla porównania
                    current_time_plus_1h = (datetime.datetime.combine(datetime.date.today(), current_time) + 
                                           datetime.timedelta(hours=1)).time()
                    
                    # Format time strings for display
                    weekday_hours = f"{weekday_open} - {weekday_close}" if weekday_open and weekday_close else "Nieznane"
                    weekend_hours = f"{weekend_open} - {weekend_close}" if weekend_open and weekend_close else "Nieznane"
                    
                    # Create hours info for display
                    hours_info = f"""
                        <p><strong>Godziny otwarcia:</strong></p>
                        <p>Dni powszednie: {weekday_hours}</p>
                        <p>Weekendy: {weekend_hours}</p>
                    """
                    
                    # Check if currently open
                    if 0 <= current_day <= 4:  # Weekday
                        if weekday_open and weekday_close:
                            try:
                                open_time = datetime.datetime.strptime(weekday_open, "%H:%M").time()
                                close_time = datetime.datetime.strptime(weekday_close, "%H:%M").time()
                                
                                # Handle overnight opening hours (close time earlier than open time)
                                if close_time < open_time:  # e.g., 06:00 to 02:00 (overnight)
                                    is_open = current_time_plus_1h >= open_time or current_time_plus_1h <= close_time
                                else:  # Normal hours, e.g., 08:00 to 20:00
                                    is_open = open_time <= current_time_plus_1h <= close_time
                            except ValueError:
                                is_open = False
                    else:  # Weekend
                        if weekend_open and weekend_close:
                            try:
                                open_time = datetime.datetime.strptime(weekend_open, "%H:%M").time()
                                close_time = datetime.datetime.strptime(weekend_close, "%H:%M").time()
                                
                                # Handle overnight opening hours (close time earlier than open time)
                                if close_time < open_time:  # e.g., 06:00 to 02:00 (overnight)
                                    is_open = current_time_plus_1h >= open_time or current_time_plus_1h <= close_time
                                else:  # Normal hours, e.g., 08:00 to 20:00
                                    is_open = open_time <= current_time_plus_1h <= close_time
                            except ValueError:
                                is_open = False

                # Create status HTML with appropriate color
                if has_hours:
                    if is_open:
                        current_status = '<p><strong style="color: green;">Otwarte</strong></p>'
                    else:
                        current_status = '<p><strong style="color: red;">Zamknięta</strong></p>'

                # Display place name if available
                place_name_html = f'<p><strong>Nazwa miejsca:</strong> {place_name}</p>' if place_name else ''

                # Zmodyfikowana logika dla wyświetlania nazwy i adresu
                if place_name:
                    # Jeśli nazwa miejsca istnieje, pokaż ją jako główny nagłówek, a adres poniżej
                    name_html = f'<h2>{place_name}</h2>'
                    address_html = f'<p><strong>Adres:</strong> {name}</p>'
                else:
                    # Jeśli nazwa miejsca nie istnieje, pokaż adres jako główny nagłówek
                    name_html = f'<h2>{name}</h2>'
                    address_html = ''

                # Poprawione bloki dla całego popup'u
                if not comments_list:
                    wholePopUp = f"""
                        <div style="width: 300px; max-height:300px, overflow-y: auto;">
                            {name_html}
                            {address_html}
                            <p>{description}</p>
                            <p><strong>Płatna:</strong> {payable}</p>
                            <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                            <p><strong>Dla niepełnosprawnych:</strong>{forDisabled}</p>
                            <p><strong>Ocena:</strong> {rating_display}</p>
                            {current_status if has_hours else ""}
                            {hours_info if has_hours else ""}
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
                            {name_html}
                            {address_html}
                            <p>{description}</p>
                            <p><strong>Płatna:</strong> {payable}</p>
                            <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                            <p><strong>Dla niepełnosprawnych:</strong>{forDisabled}</p>
                            <p><strong>Ocena:</strong> {rating_display}</p>
                            {current_status if has_hours else ""}
                            {hours_info if has_hours else ""}
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
                gc.collect()  # Force garbage collection
                
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
                    # Always add user marker regardless of location
                    self.add_marker_to_map(user_marker)
                    
                    # Rest of code for filtering and route calculation
                    # Only skip route generation if outside Opole, but still show the marker
                    if not isInOpoleProvince(user_marker['lat'], user_marker['lon']):
                        logging.warning("Użytkownik poza województwem opolskim - nie generuję trasy.")
                        user_data['current_route'] = None
                        session[user_id] = user_data
                    else:
                        # Route generation code remains the same...
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
                    name TEXT,
                    place_name TEXT,
                    description TEXT,
                    payable INTEGER,
                    onlyForClients INTEGER,
                    forDisabled INTEGER,
                    rating REAL,
                    base_rating REAL,
                    weekday_open TEXT,
                    weekday_close TEXT,
                    weekend_open TEXT,
                    weekend_close TEXT,
                    photo TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Check if place_name column exists, if not add it
                cursor.execute("PRAGMA table_info(toilets)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'place_name' not in columns:
                    cursor.execute("ALTER TABLE toilets ADD COLUMN place_name TEXT")
                
                # Create comments table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    toilet_id INTEGER,
                    comment TEXT,
                    rating REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (toilet_id) REFERENCES toilets (id)
                )
                ''')
                
                conn.commit()

    def runThePage(self):
        self.app.run(host = os.environ.get('SERVER_HOST'), port=os.environ.get('SERVER_PORT'))

    def clean_orphaned_photos(self):
        """Usuwa osierocone pliki zdjęć, które nie są powiązane z żadnym markerem"""
        try:
            # Zbierz wszystkie ścieżki zdjęć używane przez markery
            used_photos = set()
            for marker in self.original_markers:
                photo_path = marker.get('photo')
                if photo_path:
                    used_photos.add(photo_path)
            
            # Sprawdź pliki w katalogu uploads
            uploads_dir = os.path.join('static', 'uploads')
            if os.path.exists(uploads_dir):
                for filename in os.listdir(uploads_dir):
                    file_path = os.path.join('uploads', filename)
                    if file_path not in used_photos:
                        # Usuń plik, jeśli nie jest używany przez żaden marker
                        full_path = os.path.join('static', 'uploads', filename)  # POPRAWIONA ŚCIEŻKA
                        if os.path.exists(full_path):
                            os.remove(full_path)
                            logging.info(f"Usunięto osierocony plik zdjęcia: {full_path}")
        except Exception as e:
            logging.error(f"Błąd podczas czyszczenia osieroconych zdjęć: {e}")

    def update_toilet_rating(self, toilet_id, cursor):
        """Update a toilet's rating based on its comments"""
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

        def create_app():
            server = Server()
            return server.app


