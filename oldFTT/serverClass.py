import folium.plugins
import pymysql
import folium
import requests
from flask import Flask, jsonify, request, send_file, render_template_string
from markupsafe import escape
from dataService import DataServiceRestaurant as Dsr
from oldFTT.dbServiceClass import dbService as Dbs
from folium import plugins

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
            """Simple example of a fullscreen map."""
            lat, lon = get_location()
            mapbox_url = "https://api.mapbox.com/styles/v1/kvmyk9/clwtnakr2010w01qs94q19z35/tiles/256/{z}/{x}/{y}@2x?access_token=pk.eyJ1Ijoia3ZteWs5IiwiYSI6ImNsd293eGg4czEyNnEyanFlZ2lnd2Vqd2IifQ.hnwVAUb5V5WKhAKFrd0efA"
            m = folium.Map(location=[lat, lon], zoom_start=15, width = 750, height = 500,tiles=mapbox_url, attr="Mapbox attribution", overlay = False)
            return m.get_root().render()
        
        app.run(host="0.0.0.0", port=8000, debug=True)
