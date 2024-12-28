import os
import folium
import flask
import requests
import geopy
import json
import base64
import uuid
import logging
from flask import Flask, send_from_directory, jsonify, request, session, render_template
from utils import get_coordinates, get_route, find_nearest_marker, haversine, format_distance_text

logging.basicConfig(level=logging.DEBUG)

toilet_icon = os.path.join('toilet_icon.png')

class Server:
    def __init__(self):
        self.app = Flask(__name__, static_url_path='/static')
        self.app.secret_key = "twoj_sekretny_klucz"

        # Domyślna lokalizacja (Warszawa)
        self.lat, self.lon = 52.2297, 21.0122

        # Ta mapa będzie generowana w update_map(). Tworzymy ją raz tu,
        # aby nie było błędów przy pierwszym wywołaniu:
        self.m = self.create_map()

        # Globalne markery (np. z pliku data.json) – wspólne dla wszystkich
        self.markers = self.load_markers()

        # Konfiguracja ścieżek Flask
        self.setup_routes()

    def create_map(self):
        """Tworzy nową instancję folium.Map."""
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
            return send_from_directory('static/html', 'template.html')

        @self.app.route('/location', methods=['POST'])
        def location():
            """
            Ustawia aktualną pozycję użytkownika oraz wylicza trasę
            do najbliższej toalety (opcjonalnie).
            """
            data = request.json

            # Pobierz lub stwórz user_id (klucz w sesji)
            user_id = session.get('user_id')
            if not user_id:
                user_id = str(uuid.uuid4())
                session['user_id'] = user_id

            # Inicjalizacja słownika w sesji dla tego user_id (jeśli go nie ma)
            user_data = session.get(user_id, {})
            if not user_data:
                user_data = {"marker": None, "routes": []}

            # Zapisz / zaktualizuj marker użytkownika
            user_marker = {
                "lat": data['lat'],
                "lon": data['lon'],
                "name": "User Location",
                "description": "This is your location"
            }
            user_data["marker"] = user_marker
            session[user_id] = user_data  # Zapisz w sesji

            # Zaktualizuj domyślne współrzędne serwera (niekoniecznie potrzebne)
            self.lat = data['lat']
            self.lon = data['lon']

            # Opcjonalnie, policz trasę do najbliższej toalety
            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if nearest_marker:
                route = get_route(self.lat, self.lon,
                                  nearest_marker['lat'], nearest_marker['lon'])
                if route:
                    self.add_route_to_map(route)

            # Debug
            logging.debug(f"Session Data: {session}")

            return jsonify({'status': 'success', 'lat': self.lat, 'lon': self.lon})

        @self.app.route('/nearest_toilet_distance', methods=['GET'])
        def nearest_toilet_distance():
            """
            Zwraca odległość do najbliższej toalety (tekstowo).
            """
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({'status': 'error', 'message': 'User not identified'}), 404

            user_data = session.get(user_id, {})
            user_marker = user_data.get('marker')
            if not user_marker:
                return jsonify({'status': 'error', 'message': 'User location not found'}), 404

            nearest_marker = find_nearest_marker(user_marker, self.markers)
            if not nearest_marker:
                return jsonify({'status': 'error', 'message': 'No toilets found'}), 404

            route = get_route(user_marker['lat'], user_marker['lon'],
                              nearest_marker['lat'], nearest_marker['lon'])
            if not route:
                return jsonify({'status': 'error', 'message': 'Route not found'}), 404

            distance = route['routes'][0]['distance']  # w metrach
            distance_text = format_distance_text(distance)

            return jsonify({'status': 'success',
                            'distance': distance_text,
                            'name': nearest_marker['name']})

        @self.app.route('/submit', methods=['POST'])
        def submit():
            """
            Dodaje nową toaletę na podstawie danych z formularza
            i (opcjonalnie) wylicza trasę do najbliższej toalety.
            """
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
                # Dodajemy do "globalnej" listy markerów (toalety)
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
                self.save_markers()

                # Odśwież mapę (doda marker globalny)
                self.update_map()

                # Przelicz trasę do najbliższego markera
                user_id = session.get('user_id')
                if user_id:
                    user_data = session.get(user_id, {})
                    user_marker = user_data.get('marker')
                    if user_marker:
                        nearest_marker = find_nearest_marker(user_marker, self.markers)
                        if nearest_marker:
                            route = get_route(user_marker['lat'], user_marker['lon'],
                                              nearest_marker['lat'], nearest_marker['lon'])
                            if route:
                                self.add_route_to_map(route)

                return jsonify({'status': 'success', 'lat': lat, 'lon': lon})
            else:
                return jsonify({'status': 'error', 'message': 'Location not found'})

        @self.app.after_request
        def add_header(response):
            # Wyłączamy cache
            response.headers['Cache-Control'] = 'no-store'
            return response

        @self.app.route('/render_map', methods=['GET'])
        def render_map():
            # Zwraca HTML aktualnej mapy (z trasami i markerami)
            return self.update_map()

    def add_marker_to_map(self, marker):
        """
        Dodaje pojedynczy marker (słownik) do instancji folium.Map (self.m).
        """
        if marker['name'] == "User Location":
            icon = folium.CustomIcon(toilet_icon, icon_size=(50, 50), shadow_size=(50, 50))
            popup_content = f'''
                <div style="width: 300px;">
                    <h2 style="font-size: 1.5em;">User Location</h2>
                    <p style="font-size: 1em;">{marker['description']}</p>
                </div>
            '''
            folium.Marker(
                location=[marker['lat'], marker['lon']],
                popup=popup_content,
                icon=icon
            ).add_to(self.m)
        else:
            iconToilet = folium.CustomIcon(toilet_icon, icon_size=(50, 50), shadow_size=(50, 50))
            name = marker.get('name', 'Unknown')
            description = marker.get('description', 'No description')
            payable = "TAK" if marker.get('payable', False) else "NIE"
            onlyForClients = "TAK" if marker.get('onlyForClients', False) else "NIE"
            rating = marker.get('rating', 'Brak oceny')
            photo_base64 = marker.get('photo', None)
            photo_html = (f'<img src="data:image/png;base64,{photo_base64}" '
                          f'style="width: 100%; height: auto;">') if photo_base64 else ''
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
            folium.Marker(
                location=[marker['lat'], marker['lon']],
                popup=wholePopUp,
                icon=iconToilet
            ).add_to(self.m)

    def add_route_to_map(self, route):
        """
        Zamiast rysować trasę od razu na mapie (co spowoduje, że wszyscy ją zobaczą),
        zapisujemy ją w sesji dla konkretnego użytkownika.
        """
        user_id = session.get('user_id')
        if not user_id:
            # Brak user_id = brak możliwości zapisu per użytkownik
            logging.warning("No user_id in session – cannot store route.")
            return

        user_data = session.get(user_id, {})
        if 'routes' not in user_data:
            user_data['routes'] = []

        user_data['routes'].append(route)
        session[user_id] = user_data

        # Na koniec można wywołać update_map(), by od razu zaktualizować widok
        self.update_map()

    def update_map(self):
        """
        Tworzy nowy obiekt mapy (czyści poprzedni stan).
        Dodaje:
          - Globalne markery (self.markers)
          - Marker użytkownika (z sesji)
          - Trasy użytkownika (z sesji)
        Zwraca wygenerowany kod HTML.
        """
        self.m = self.create_map()

        # 1. Dodajemy "globalne" markery (toalety z pliku data.json)
        for marker in self.markers:
            self.add_marker_to_map(marker)

        # 2. Dodajemy marker i trasy aktualnego użytkownika
        user_id = session.get('user_id')
        if user_id:
            user_data = session.get(user_id, {})

            # a) Marker użytkownika
            user_marker = user_data.get('marker')
            if user_marker:
                self.add_marker_to_map(user_marker)

            # b) Trasy użytkownika
            for route in user_data.get('routes', []):
                coordinates = [
                    (coord[1], coord[0])
                    for coord in route['routes'][0]['geometry']['coordinates']
                ]
                logging.info(f"Coordinates: {coordinates}")

                distance = route['routes'][0]['distance']  # metry
                logging.info(f"Distance: {distance}")

                distance_text = f"{distance / 1000:.2f} km"
                logging.info(f"Distance Text: {distance_text}")

                # Rysujemy polilinię
                folium.PolyLine(
                    locations=coordinates,
                    color='red',
                    weight=5,
                    opacity=0.7
                ).add_to(self.m)

                # Dodajmy napis z odległością w połowie trasy
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

        # Zwróć wygenerowany HTML
        return self.m._repr_html_()

    def save_markers(self):
        """Zapisuje 'globalne' markery (toalety) do pliku data.json."""
        with open(os.path.join('data', 'data.json'), 'w', encoding='utf-8') as file:
            json.dump(self.markers, file, ensure_ascii=False, indent=4)

    def runThePage(self):
        self.app.run(host="0.0.0.0", port=21088)
