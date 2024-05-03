from flask import Flask, jsonify, request, send_file

class Server():

    def __init__(self):
        self.data = None
    def get_data(self):
        return self.data
    def set_data(self, data):
        self.data = data

    def runThePage(self, data):
        app = Flask(__name__)

        @app.route('/hello')

        def hello():
            return data

        app.run(host="0.0.0.0", port=8000, debug=True)
