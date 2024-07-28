import folium, flask, requests
from flask import Flask

toilet_icon = "C:\\Users\\kubak\\Desktop\\toilet_icon.png"


def get_location():
    response = requests.get('http://ip-api.com/json/')
    data = response.json()
    lat = data['lat']
    lon = data['lon']
    return lat, lon

class Server():

    def __init__(self):
        self.data = None
    def get_data(self):
        return self.data
    def set_data(self, data):
        self.data = data

    def runThePage(self):
        app = Flask(__name__)   

        @app.route('/')
        def fullscreen():
            lat, lon = get_location()
            m = folium.Map(location= [lat, lon],tiles= "Cartodb positron",zoom_start=15, overlay = False)
            icon = folium.CustomIcon(toilet_icon, icon_size=(50,50))
            folium.Marker(location=[lat, lon], icon=icon).add_to(m)
            return m.get_root().render()
        
        app.run(host="0.0.0.0", port=8000, debug=True)
    
run = Server()

run.runThePage()

