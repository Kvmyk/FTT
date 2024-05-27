from flask import Flask, jsonify, request, send_file, render_template_string
from markupsafe import escape

from dataService import DataServiceRestaurant as Dsr
from dbServiceClass import dbService as Dbs
import pymysql
import folium


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
            m = folium.Map(tiles='http://{s}.tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png', attr='My Data Attribution')
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
