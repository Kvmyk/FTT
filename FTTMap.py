import folium, flask, requests, os
from flask import Flask, send_from_directory, Response

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

            # setting up the custom icon

            icon = folium.CustomIcon(toilet_icon, icon_size=(50,50))

            # setting the icon on map

            folium.Marker(location=[lat, lon], icon=icon).add_to(m)
            m.save('map.html')

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
                // Tutaj możesz dodać kod do obsługi danych wprowadzonych przez użytkownika
                var userInput = document.getElementById('userInput').value;
                console.log(userInput); // Przykład wyświetlenia wprowadzonych danych w konsoli
                document.getElementById('myModal').style.display = 'none';
                }
                </script>
                </body>
                </html>
                """)

            return send_from_directory('.', 'map.html',)
        app.run(host="0.0.0.0", port=8000, debug=True)


if __name__ == "__main__":   
    run = Server()
    run.runThePage()

