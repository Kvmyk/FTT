from flask import Flask, jsonify, request, send_file, render_template_string
from markupsafe import escape


class Server():

    def __init__(self):
        self.data = None
    def get_data(self):
        return self.data
    def set_data(self, data):
        self.data = data

    def runThePage(self, data):
        app = Flask(__name__)

        @app.route('/')

        def get_data():
            output = ""
            for i in data:
                rating = i[1]
                place = i[2]
                street = i[3]
                city = i[4]
                country = i[5]
                desc = i[6]
                output += f"<h2>{place}</h2><p>Rating: {rating}<br>Street: {street}<br>City: {city}<br>Country: {country}<br>Description: {desc}</p><hr>"
            return render_template_string(output)

        app.run(host="0.0.0.0", port=8000, debug=True)
