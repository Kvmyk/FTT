from flask import Flask, jsonify, request, send_file, render_template_string
from markupsafe import escape

from dataService import DataServiceRestaurant as Dsr
from dbServiceClass import dbService as Dbs
import pymysql


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

        def get_data():

            clientData = Dsr(6, "Bar", "First Street", "Boston", "USA", "Nice place")
            db = Dbs(clientData.dataList)
            data = db.selectData()

            output = """
    <html>
        <head>
            <title>Moja strona</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: lightblue;
                }
                 .header {
                    background-color: blue;
                    color: white;
                    padding: 10px;
                    text-align: center;
                }
                .content {
                    margin: 15px;
                    background-color: white;
                    padding: 10px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th, td {
                    border: 1px solid black;
                    padding: 10px;
                    text-align: left;
                }
                th {
                    background-color: blue;
                    color: white;
                } </style>
        </head>
        <body>
            <div class="header">
                <h1>Witaj na mojej stronie!</h1>
            </div>
            <div class="content">
                <table>
                    <tr>
                        <th>Rating</th>
                        <th>Place</th>
                        <th>Street</th>
                        <th>City</th>
                        <th>Country</th>
                        <th>Description</th>
                    </tr>
    """
            for i in data:
                rating = i[1]
                place = i[2]
                street = i[3]
                city = i[4]
                country = i[5]
                desc = i[6]
                output += f"<tr><td>{rating}</td><td>{place}</td><td>{street}</td><td>{city}</td><td>{country}</td><td>{desc}</td></tr>"
            output += """
                </table>
            </div>
        </body>
    </html>
    """    
            return render_template_string(output)
            
        app.run(host="0.0.0.0", port=8000, debug=True)
