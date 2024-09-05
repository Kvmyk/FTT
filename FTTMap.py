import folium, flask, requests, os, geopy, json
from flask import Flask, send_from_directory, Response, jsonify, request
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="test")
toilet_icon = "C:\\Users\\kubak\\Desktop\\FTT\\toilet_icon.png"

def get_location():
    response = requests.get('http://ip-api.com/json/')
    data = response.json()
    lat = data['lat']
    lon = data['lon']
    return lat, lon

def get_coordinates(location):
    location = geolocator.geocode(location)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

class Server():
    def __init__(self):
        self.data = None
        self.app = Flask(__name__)
        self.lat, self.lon = get_location()
        self.m = folium.Map(location=[self.lat, self.lon], tiles="Cartodb positron", zoom_start=15, overlay=False)
        self.markers=self.load_markers()
        self.setup_routes()

    # loading markers from a file

    def load_markers(self):
        with open('data/data.json', 'r', encoding='utf-8') as file:
            return json.load(file)

    # setting up routes for the server

    def setup_routes(self):
        @self.app.route('/')
        def fullscreen():
            self.save_markers()
            self.load_markers()
            self.update_map()
            self.save_map()
            return send_from_directory('.', 'map.html')

        @self.app.route('/submit', methods=['POST'])
        def submit():
            data = request.json
            userInput = data['userInput']
            lat, lon = get_coordinates(userInput)
            if lat and lon:
                new_marker = {
                    "lat":lat,
                    "lon":lon,
                    "name":userInput
                }
                self.markers.append(new_marker)  
                self.update_map()
                self.save_map()
                self.save_markers()  
                return jsonify({'status': 'success', 'lat': lat, 'lon': lon})
            else:
                return jsonify({'status': 'error', 'message': 'Nie znaleziono lokalizacji'})
   
    # updating map with new markers

    def update_map(self):
        self.m = folium.Map(location=[self.lat, self.lon], tiles="Cartodb positron", zoom_start=15, overlay=False)
        for marker in self.markers:
            iconToilet = folium.CustomIcon(toilet_icon, icon_size=(50, 50), shadow_size=(50, 50))
            name = marker.get('name', 'Unknown')
            folium.Marker(location=[marker['lat'], marker['lon']],popup=name, icon=iconToilet).add_to(self.m)

    # saving map to a file and adding a template to it

    def save_map(self):
            self.m.save('map.html')
            with open('template.html', 'r', encoding='utf-8') as template_file:
                template_content = template_file.read()
            with open('map.html', 'a', encoding='utf-8') as file:
                file.write(template_content)
    
    # saving markers on a map

    def save_markers(self):
        with open('data/data.json', 'w', encoding='utf-8') as file:
            json.dump(self.markers, file, ensure_ascii=False, indent=3)

    def runThePage(self):
        self.app.run(host="0.0.0.0", port=8000, debug=True)

if __name__ == "__main__":   
    run = Server()
    run.runThePage()