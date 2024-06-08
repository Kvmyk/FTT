from flask import Flask, jsonify, request, send_file, render_template_string
from markupsafe import escape

from dataService import DataServiceRestaurant as Dsr
from dbServiceClass import dbService as Dbs
import pymysql
import folium
import requests

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
            m = folium.Map(location=[lat,lon],tiles=mapbox_url, attr="Mapbox", zoom_start=15)
            return m.get_root().render()
        @app.route("/iframe")
        def iframe():
            """Embed a map as an iframe on a page."""
            m = folium.Map()

            # set the iframe width and height
            m.get_root().width = "800px"
            m.get_root().height = "600px"
            iframe = m.get_root()._repr_html_()

            return render_template_string(
                """
                    <!DOCTYPE html>
                    <html>
                        <head></head>
                        <body>
                            <h1>Using an iframe</h1>
                            {{ iframe|safe }}
                        </body>
                    </html>
                """,
                iframe=iframe,
            )

        @app.route("/components")
        def components():
            """Extract map components and put those on a page."""
            m = folium.Map(
                width=800,
                height=600,
            )

            m.get_root().render()
            header = m.get_root().header.render()
            body_html = m.get_root().html.render()
            script = m.get_root().script.render()

            return render_template_string(
                """
                    <!DOCTYPE html>
                    <html>
                        <head>
                            {{ header|safe }}
                        </head>
                        <body>
                            <h1>Using components</h1>
                            {{ body_html|safe }}
                            <script>
                                {{ script|safe }}
                            </script>
                        </body>
                    </html>
                """,
                header=header,
                body_html=body_html,
                script=script,
            )
        app.run(host="0.0.0.0", port=8000, debug=True)
