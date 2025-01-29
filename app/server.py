import os
import folium
import flask
import requests
import geopy
import json
import base64
import uuid
import logging

from flask import Flask, send_from_directory, jsonify, request, session
from utils import get_coordinates, get_route, find_nearest_marker, haversine, format_distance_text

logging.basicConfig(level=logging.DEBUG)

# Ścieżka do pliku z ikoną (w katalogu static)
toilet_icon = os.path.join('toilet_icon.png')

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        self.app.secret_key = "twoj_sekretny_klucz"  # klucz do sesji - niezbędny

        # Domyślne współrzędne (np. Warszawa) - użyte TYLKO gdy user nie ustawił własnych
        self.default_lat = 52.2297
        self.default_lon = 21.0122

        # Ładujemy globalne markery z pliku data.json (toalety)
        self.markers = self.load_markers()

        # Tworzymy na start pustą mapę, ale i tak będziemy ją przeładowywać w update_map()
        self.m = self.create_map()

        self.setup_routes()

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

    def add_marker_to_map(self, marker):
        """
        Dodaje POJEDYNCZY marker do mapy self.m.
        """
        if marker.get('name') == "User Location":
            # Marker użytkownika
            icon = folium.CustomIcon(
                toilet_icon,
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

            # Marker toalety (globalny)
            iconToilet = folium.CustomIcon(
                toilet_icon, 
                icon_size=(50, 50), 
                shadow_size=(50, 50)
            )
            lat = marker['lat']
            lon = marker['lon']
            existing_marker = next((m for m in self.markers if m['lat'] == lat and m['lon'] == lon), None)

            if existing_marker:
                # Aktualizujemy tylko istniejący marker (np. komentarz i ocenę)
                description = marker.get('description')
                rating = marker.get('rating')
                if description and rating:
                    comments = existing_marker.setdefault('comments', [])
                    if not any(c for c in comments if c['comment'] == description and c['rating'] == rating):
                        comments.append({'comment': description, 'rating': rating})
                    existing_marker['rating'] = rating
            else:
                

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
                    <div id='comments-{marker['lat']}-{marker['lon']}'
                        style='max-height: 200px; overflow-y: auto; font-family: Roboto, sans-serif;'>
                """
                
                for c in comments_list:
                    comments_html += f"""
                        <p><strong>Ocena:</strong> {c.get('rating')}</p>
                        <p>{c.get('comment')}</p>
                        <hr style="border-top: 1px solid #ccc;" />
                    """
                comments_html += "</div>"

                # Użycie współrzędnych jako identyfikatora
                comment_button_html = f"""
                    <button onclick="window.parent.openCommentModal({lat}, {lon})" 
                            style="width: 80%; background-color: red; color: white; padding: 14px 20px; margin: 8px 0; border: none; border-radius: 4px; cursor: pointer; font-family: 'Roboto', sans-serif; font-weight: 300;">
                        Dodaj komentarz
                    </button>
                """
            if not comments_list:
                wholePopUp = f"""
                    <div style="width: 300px;">
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
            else:
                wholePopUp = f"""
                    <div style="width: 300px;">
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
                        {comment_button_html}
                    </div>
                """
            folium.Marker(
                location=[lat, lon],
                popup=wholePopUp,
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
                    color='red',
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
