import folium, flask, requests, os, geopy
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
        self.iconToilet = folium.CustomIcon(toilet_icon, icon_size=(50, 50))
        self.markers=[]
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def fullscreen():
            self.save_map()
            return send_from_directory('.', 'map.html')

        @self.app.route('/submit', methods=['POST'])
        def submit():
            data = request.json
            userInput = data['userInput']
            lat, lon = get_coordinates(userInput)
            if lat and lon:
                self.markers.append((lat, lon))  # Dodaj marker do listy
                self.update_map()
                self.save_map()  
                return jsonify({'status': 'success', 'lat': lat, 'lon': lon})
            else:
                return jsonify({'status': 'error', 'message': 'Nie znaleziono lokalizacji'})
    def update_map(self):
        # Usuń wszystkie markery z mapy i dodaj je ponownie
        self.m = folium.Map(location=[self.lat, self.lon], tiles="Cartodb positron", zoom_start=15, overlay=False)
        for lat, lon in self.markers:
            folium.Marker(location=[lat, lon], icon=self.iconToilet).add_to(self.m)

    def save_map(self):
            self.m.save('map.html')
            with open('map.html', 'a', encoding='utf-8') as file:
                file.write("""
                <!DOCTYPE html>
                <html>
                <head>
                <meta charset="UTF-8">
                <style>
                .circle-plus {
                  width: 40px;
                  height: 40px;
                  background-color: white;
                  border: 3px solid red;
                  border-radius: 50%;
                  color: red;
                  text-align: center;
                  line-height: 34px;
                  font-size: 28px;
                  position: fixed;
                  top: 10px;
                  right: 10px;
                  z-index: 1000;
                }
                .circle-plus:hover {
                  transform: scale(1.1); /* Dodano */
                  background-color: #EEEEEE;    
                }
                #myModal input[type="text"] {
                    width: 80%;
                    padding: 10px;
                    margin: 10px 0;
                    display: inline-block;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    box-sizing: border-box;
                }
                #myModal button {
                    width: 80%;
                    background-color: red;
                    color: white;
                    padding: 14px 20px;
                    margin: 8px 0;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                #myModal button:hover {
                    background-color: #C92704;
                }
                </style>
                </head>
                <body>
                <div class="circle-plus">+</div>
                <!-- Modal -->
                <div id="myModal" style="display:none; position:fixed; z-index:1001; left:50%; top:50%; transform:translate(-50%, -50%); background-color:white; padding:20px; border-radius:5px; box-shadow: 0 5px 15px rgba(0,0,0,0.3);">
                <span id="closeModal" style="cursor:pointer; float:right; font-size:20px;">&times;</span>
                <input type="text" id="userInput" placeholder="Wpisz coś...">
                <button onclick="submitModal()">Gotowe</button>
                </div>
                <script>
                document.querySelector('.circle-plus').addEventListener('click', function() {
                document.getElementById('myModal').style.display = 'block';
                });
                document.getElementById('closeModal').addEventListener('click', function() {
                document.getElementById('myModal').style.display = 'none';
                });
                function submitModal() {
                    var userInput = document.getElementById('userInput').value;
                    console.log(userInput); // Wyświetlenie danych w konsoli                    // Używanie AJAX do wysłania danych do serwera Flask
                    fetch('/submit', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ userInput: userInput }), // Wysyłanie danych jako JSON
                    })
                    .then(response => response.json())
                    .then(data => {
                        console.log('Success:', data);
                            if (data.status === 'success') {
                            // Odśwież mapę po dodaniu markera
                            window.location.reload();
                        } else {
                            alert(data.message);
                        }
                    })
                    .catch((error) => {
                        console.error('Error:', error);
                    });
                
                    document.getElementById('myModal').style.display = 'none';
                }
                </script>
                </body>
                </html>
                """)
                
    def runThePage(self):
        self.app.run(host="0.0.0.0", port=8000, debug=True)

if __name__ == "__main__":   
    run = Server()
    run.runThePage()