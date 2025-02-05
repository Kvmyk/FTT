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
import redis
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

        self.app.config['SESSION_TYPE'] = 'redis'
        self.app.config['SESSION_PERMANENT'] = False
        self.app.config['SESSION_USE_SIGNER'] = True
        self.app.config['SESSION_REDIS'] = redis(host='localhost', port=6379)

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

        @self.app.route('/nearest_toilet_distance', methods=['GET'])
        def nearest_toilet_distance():
            """
            Dodatkowy endpoint, który zwraca odległość do najbliższej toalety
            (np. żeby wyświetlić w popupie).
            """
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({'status': 'error', 'message': 'User not identified'}), 404

            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if not user_marker:
                return jsonify({'status': 'error', 'message': 'No user marker set'}), 404

            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if not nearest_marker:
                return jsonify({'status': 'error', 'message': 'No toilets found'}), 404

            route = get_route(
                user_marker['lat'], user_marker['lon'],
                nearest_marker['lat'], nearest_marker['lon']
            )
            if not route:
                return jsonify({'status': 'error', 'message': 'Route not found'}), 404

            distance = route['routes'][0]['distance']  # metry
            distance_text = format_distance_text(distance)

            return jsonify({
                'status': 'success',
                'distance': distance_text,
                'name': nearest_marker['name']
            })

        @self.app.route('/submit', methods=['POST'])
        def submit():
            """
            Dodaje nową toaletę do globalnej listy i zapisuje do data.json.
            Następnie, jeśli user ma swój marker, przeliczamy trasę do nowego 
            (albo najbliższego) markera.
            """
            data = request.form
            userInput = data.get('userInput', '')
            description = data.get('description', '')
            payable = data.get('payable', 'false').lower() == 'true'
            onlyForClients = data.get('onlyForClients', 'false').lower() == 'true'
            rating = data.get('rating', '0')
            photo = request.files.get('photos')  # może być None
            photo_base64 = None
            if photo:
                photo_base64 = base64.b64encode(photo.read()).decode('utf-8')

            # Ustalenie współrzędnych na podstawie userInput (np. nazwy miejsca)
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

                # Dodajemy do globalnej listy
                self.markers.append(new_marker)
                # Zapisujemy do pliku data.json
                self.save_markers()

                # Odświeżamy mapę (opcjonalnie)
                self.update_map()

                # Ewentualnie wyliczamy trasę do najbliższego
                user_id = session.get('user_id')
                if user_id:
                    user_data = session.get(user_id, {})
                    user_marker = user_data.get('marker')
                    if user_marker and len(self.markers) > 0:  # Sprawdzamy, czy jest więcej niż jeden marker
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

            for marker in self.markers:
                if marker['lat'] == lat and marker['lon'] == lon:
                    marker.setdefault('comments', []).append({'comment': comment, 'rating': rating})
                    self.save_markers()
                    return jsonify({'status': 'success'})

            return jsonify({'status': 'error', 'message': 'Marker not found'}), 404

        @self.app.route('/navigate', methods=['POST'])
        def navigate():
            data = request.json
            user_id = session.get('user_id')
            
            if not user_id:
                user_id = str(uuid.uuid4())
                session['user_id'] = user_id
            
            # Aktualizuj marker użytkownika
            user_data = session.get(user_id, {})
            user_marker = {
                "lat": data['user_lat'],
                "lon": data['user_lon'],
                "name": "User Location",
                "description": "This is your location"
            }
            user_data['marker'] = user_marker
            
            # Wyznacz trasę do wybranej toalety
            route = get_route(
                data['user_lat'], 
                data['user_lon'],
                data['target_lat'], 
                data['target_lon']
            )
            
            if route:
                user_data['current_route'] = route
                session[user_id] = user_data  # Zapisz dane w sesji
                self.update_map()  # Zaktualizuj mapę
                return jsonify({'status': 'success'})
            
            return jsonify({'status': 'error', 'message': 'Could not calculate route'})

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

            if is_within_range:
                onclick_attr = f"window.parent.navigateToToilet({lat}, {lon})"
                disabled_attr = ""
            else:
                onclick_attr = ""
                disabled_attr = 'disabled="disabled"'

            navigate_button_html = f"""
                <button onclick="window.parent.navigateToToilet({lat}, {lon})"
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
                        >
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
            lat = marker['lat']
            lon = marker['lon']
            existing_marker = next((m for m in self.markers if m['lat'] == lat and m['lon'] == lon), None)

            if existing_marker and marker != existing_marker:
                # Dodaj komentarz i ocenę do istniejącego markera
                description = marker.get('description')
                rating = marker.get('rating')
                if description and rating:
                    comments = existing_marker.setdefault('comments', [])
                    # Dodaj komentarz tylko, jeśli go wcześniej nie było
                    if not any(c for c in comments if c['comment'] == description and c['rating'] == rating):
                        comments.append({'comment': description, 'rating': rating})
                    existing_marker['rating'] = rating  # Aktualizuj ocenę
                    return
                    
            name = marker.get('name', 'Unknown')
            description = marker.get('description', 'No description')
            payable = "TAK" if marker.get('payable', False) else "NIE"
            onlyForClients = "TAK" if marker.get('onlyForClients', False) else "NIE"
            rating = marker.get('rating', 'Brak oceny')
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
            if not comments_list:
                wholePopUp = f"""
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
                        <p><strong>Ocena:</strong> {rating}</p>
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

        # Tworzymy mapę z uwzględnieniem centrum na user_marker (o ile jest)
        self.m = self.create_map(center_lat, center_lon)

        # Dodajemy globalne markery (toalety)
        for marker in self.markers:
            self.add_marker_to_map(marker)

        # Dodajemy marker + trasę użytkownika
        if user_id:
            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if user_marker:
                self.add_marker_to_map(user_marker)

            route = user_data.get('current_route')
            if route and len(self.markers) > 0:
                coordinates = [
                    (coord[1], coord[0])
                    for coord in route['routes'][0]['geometry']['coordinates']
                ]
                distance = route['routes'][0]['distance']  # w metrach
                distance_text = f"{distance / 1000:.2f} km"

                # Rysujemy czerwoną polilinię
                folium.PolyLine(
                    locations=coordinates,
                    color='#d00000',
                    weight=5,
                    opacity=0.7
                ).add_to(self.m)

                # Znacznik z odległością w połowie trasy
                mid_point_index = len(coordinates) // 2
                mid_point = coordinates[mid_point_index]
                offset_latitude = 0.0007  # przesuwamy napis troszkę do góry
                offset_longitude = 0.0007  # przesuwamy napis troszkę w bok
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

        # Zwracamy kod HTML gotowy do wstawienia w przeglądarkę (w <div id="map">)
        return self.m._repr_html_()

    def runThePage(self):
        self.app.run(host = "2a01:4f9:2b:289c::130", port=80)
