import folium, flask, requests, os
from flask import Flask, send_from_directory

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

            with open('map.html', 'a') as file:
                file.write("""
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
                </style>
                <div class="circle-plus">+</div>
                """)

            return send_from_directory('.', 'map.html')
        
        app.run(host="0.0.0.0", port=8000, debug=True)


if __name__ == "__main__":   
    run = Server()
    run.runThePage()

