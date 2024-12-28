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

# Ikona toalety (ścieżka do pliku w static)
toilet_icon = os.path.join('toilet_icon.png')

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        self.app.secret_key = "twoj_sekretny_klucz"  # klucz sesji - KONIECZNIE

        # Domyślna lokalizacja (np. Warszawa)
        self.lat, self.lon = 52.2297, 21.0122

        # Wczytaj markery z pliku data.json (są wspólne dla wszystkich)
        self.markers = self.load_markers()

        # Stwórz instancję mapy (można też tworzyć w update_map)
        self.m = self.create_map()

        # Zainicjuj ścieżki/endpointy Flask
        self.setup_routes()

    def create_map(self):
        """Tworzy nowy obiekt folium.Map (pusta mapa)."""
        return folium.Map(
            location=[self.lat, self.lon],
            tiles="Cartodb positron",
            zoom_start=15,
            overlay=False,
            min_zoom=2,
            max_zoom=18
        )

    def load_markers(self):
        """Ładuje listę toalet (markerów) z pliku data.json."""
        try:
            with open(os.path.join('data', 'data.json'), 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
                else:
                    logging.error("data.json nie zwraca listy.")
                    return []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Nie udało się wczytać data.json: {e}")
            return []

    def save_markers(self):
        """Zapisuje bieżącą listę markerów (globalnych toalet) do pliku data.json."""
        try:
            with open(os.path.join('data', 'data.json'), 'w', encoding='utf-8') as file:
                json.dump(self.markers, file, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Błąd zapisu do data.json: {e}")

    def setup_routes(self):
        """
        Definiuje wszystkie endpointy:
            - /: serwuje plik HTML (mapa i interfejs),
            - /location: POST – ustawia pozycję użytkownika i liczy trasę,
            - /nearest_toilet_distance: GET – zwraca odległość do najbliższej toalety,
            - /submit: POST – dodaje nowy marker (toaletę),
            - /render_map: GET – zwraca HTML z aktualną mapą (markery i trasa),
            - after_request i inne pomocnicze.
        """

        @self.app.route('/')
        def fullscreen():
            # Serwujemy np. plik template.html ze statica
            return send_from_directory('static/html', 'template.html')

        @self.app.route('/location', methods=['POST'])
        def location():
            """
            Ustawia aktualną pozycję użytkownika + oblicza trasę do najbliższego markera.
            """
            data = request.json  # zakładamy JSON {lat: ..., lon: ...}

            # Sprawdź / utwórz unikalne user_id w sesji
            user_id = session.get('user_id')
            if not user_id:
                user_id = str(uuid.uuid4())
                session['user_id'] = user_id

            # Wczytujemy (lub tworzymy) słownik z danymi usera
            user_data = session.get(user_id, {})
            if not user_data:
                user_data = {"marker": None, "current_route": None}

            # Zapiszmy aktualny marker (pozycję) użytkownika
            user_marker = {
                "lat": data['lat'],
                "lon": data['lon'],
                "name": "User Location",
                "description": "This is your location"
            }
            user_data["marker"] = user_marker

            # Zapisz w sesji
            session[user_id] = user_data

            # Możemy też ustawić globalne self.lat/lon (niekonieczne)
            self.lat = data['lat']
            self.lon = data['lon']

            # Liczymy trasę do najbliższego markera
            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if nearest_marker:
                route = get_route(
                    user_marker['lat'], user_marker['lon'],
                    nearest_marker['lat'], nearest_marker['lon']
                )
                if route:
                    self.add_route_to_map(route)

            logging.debug(f"SESSION: {session}")
            return jsonify({'status': 'success', 'lat': self.lat, 'lon': self.lon})

        @self.app.route('/nearest_toilet_distance', methods=['GET'])
        def nearest_toilet_distance():
            """
            Zwraca informację o odległości do najbliższej toalety
            (używane np. na starcie do wyświetlenia popupu).
            """
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({'status': 'error', 'message': 'User not identified'}), 404

            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if not user_marker:
                return jsonify({'status': 'error', 'message': 'User location not set'}), 404

            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if not nearest_marker:
                return jsonify({'status': 'error', 'message': 'No toilets found'}), 404

            # Liczymy trasę "na żądanie" (nie musi być to ta sama, co w user_data, bo i tak jest najbliższa)
            route = get_route(
                user_marker['lat'], user_marker['lon'],
                nearest_marker['lat'], nearest_marker['lon']
            )
            if not route:
                return jsonify({'status': 'error', 'message': 'Route not found'}), 404

            distance = route['routes'][0]['distance']  # w metrach
            distance_text = format_distance_text(distance)

            return jsonify({
                'status': 'success',
                'distance': distance_text,
                'name': nearest_marker['name']
            })

        @self.app.route('/submit', methods=['POST'])
        def submit():
            """
            Dodaje nową toaletę (marker) do listy globalnej (i do pliku data.json).
            Następnie (opcjonalnie) wylicza trasę dla aktualnego usera do najbliższej toalety.
            """
            data = request.form
            userInput = data.get('userInput', '')
            description = data.get('description', '')
            payable = data.get('payable', 'false').lower() == 'true'
            onlyForClients = data.get('onlyForClients', 'false').lower() == 'true'
            rating = data.get('rating', '0')
            photo = request.files.get('photos')  # ewentualnie None

            if photo:
                photo_base64 = base64.b64encode(photo.read()).decode('utf-8')
            else:
                photo_base64 = None

            # Ustalenie współrzędnych nowej toalety
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

                # Dodajemy do globalnej listy i zapisujemy w data.json
                self.markers.append(new_marker)
                self.save_markers()

                # Ewentualnie odświeżamy mapę
                self.update_map()

                # Przelicz trasę do najbliższej toalety (dla tego użytkownika)
                user_id = session.get('user_id')
                if user_id:
                    user_data = session.get(user_id, {})
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

        @self.app.after_request
        def add_header(response):
            # Wyłączenie cache
            response.headers['Cache-Control'] = 'no-store'
            return response

        @self.app.route('/render_map', methods=['GET'])
        def render_map():
            """
            Zwraca HTML z aktualną mapą (z naniesionym markerem usera + trasą + globalnymi toaletami).
            """
            return self.update_map()

    def add_marker_to_map(self, marker):
        """
        Dodaje JEDEN marker (słownik) do folium.Map (self.m).
        Różne ikony i popupy w zależności czy to 'User Location', czy 'toaleta'.
        """
        if marker.get('name') == "User Location":
            icon = folium.CustomIcon(
                toilet_icon,  # Możesz wstawić inny plik, np. "user_icon.png"
                icon_size=(50, 50),
                shadow_size=(50, 50)
            )
            popup_content = f"""
                <div style="width: 300px;">
                    <h2 style="font-size: 1.5em;">User Location</h2>
                    <p style="font-size: 1em;">{marker.get('description', '')}</p>
                </div>
            """
            folium.Marker(
                location=[marker['lat'], marker['lon']],
                popup=popup_content,
                icon=icon
            ).add_to(self.m)
        else:
            # Toaleta
            iconToilet = folium.CustomIcon(toilet_icon, icon_size=(50, 50), shadow_size=(50, 50))
            name = marker.get('name', 'Unknown')
            description = marker.get('description', 'No description')
            payable = "TAK" if marker.get('payable', False) else "NIE"
            onlyForClients = "TAK" if marker.get('onlyForClients', False) else "NIE"
            rating = marker.get('rating', 'Brak oceny')
            photo_base64 = marker.get('photo', None)

            photo_html = ""
            if photo_base64:
                photo_html = f'''
                    <img src="data:image/png;base64,{photo_base64}"
                         style="width: 100%; height: auto;">
                '''

            wholePopUp = f"""
                <div style="width: 300px;">
                    <h2 style="font-size: 1.5em;">{name}</h2>
                    <p style="font-size: 1em;">{description}</p>
                    <p><strong>Płatna:</strong> {payable}</p>
                    <p><strong>Tylko dla klientów:</strong> {onlyForClients}</p>
                    <p><strong>Ocena:</strong> {rating}</p>
                    {photo_html}
                </div>
            """
            folium.Marker(
                location=[marker['lat'], marker['lon']],
                popup=wholePopUp,
                icon=iconToilet
            ).add_to(self.m)

    def add_route_to_map(self, route):
        """
        Zapisuje JEDNĄ trasę w sesji użytkownika (nadpisuje ewentualną poprzednią).
        """
        user_id = session.get('user_id')
        if not user_id:
            logging.warning("No user_id in session – cannot store route.")
            return

        user_data = session.get(user_id, {})
        user_data['current_route'] = route
        session[user_id] = user_data

        # Opcjonalnie możesz od razu wywołać update_map(), by natychmiast zaktualizować
        self.update_map()

    def update_map(self):
        """
        Buduje nową mapę, dodaje:
            - globalne markery (toalety z data.json),
            - marker użytkownika (z sesji),
            - JEDNĄ trasę użytkownika (z sesji).
        Zwraca _repr_html_ (kod HTML) do wstawienia w <div id="map">.
        """
        # 1. Stwórz nową, pustą mapę
        self.m = self.create_map()

        # 2. Dodaj globalne markery (toalety)
        for marker in self.markers:
            self.add_marker_to_map(marker)

        # 3. Dodaj marker i trasę aktualnego użytkownika (o ile jest user_id)
        user_id = session.get('user_id')
        if user_id:
            user_data = session.get(user_id, {})

            # Marker
            user_marker = user_data.get('marker')
            if user_marker:
                self.add_marker_to_map(user_marker)

            # Trasa (tylko jedna, 'current_route')
            route = user_data.get('current_route')
            if route:
                coordinates = [
                    (coord[1], coord[0])
                    for coord in route['routes'][0]['geometry']['coordinates']
                ]
                distance = route['routes'][0]['distance']
                distance_text = f"{distance/1000:.2f} km"

                # Rysuj polilinię
                folium.PolyLine(
                    locations=coordinates,
                    color='red',
                    weight=5,
                    opacity=0.7
                ).add_to(self.m)

                # Dodaj znacznik z odległością w połowie trasy
                mid_point_index = len(coordinates) // 2
                mid_point = coordinates[mid_point_index]
                offset_latitude = 0.0007
                mid_point_with_offset = [mid_point[0] + offset_latitude, mid_point[1]]

                folium.Marker(
                    location=mid_point_with_offset,
                    icon=folium.DivIcon(
                        html=f'''
                            <div style="font-size: 12px; color: red; width: 100px;">
                                {distance_text}
                            </div>
                        '''
                    )
                ).add_to(self.m)

        # 4. Zwróć HTML
        return self.m._repr_html_()

    def runThePage(self):
        """
        Uruchamia serwer Flask na określonym porcie (lub 5000, jeśli nic nie podasz).
        """
        self.app.run(host="0.0.0.0", port=21088)
