import sys
import json
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
from PyQt5.QtCore import QThread
import os
import dotenv
from geopy import distance
from PyQt5.QtCore import QTimer

import requests


dotenv.load_dotenv()



mapbox_token = os.getenv('api_key')
start_coordinates = [39.290273, 8.560654]  # Define your start coordinates

html = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
    </style>
</head>
<body>
<div id='map'></div>
<script src='https://api.mapbox.com/mapbox-gl-js/v2.6.1/mapbox-gl.js'></script>
<link href='https://api.mapbox.com/mapbox-gl-js/v2.6.1/mapbox-gl.css' rel='stylesheet' />
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
    mapboxgl.accessToken = '{0}';
    var map = new mapboxgl.Map({{
        container: 'map',
        style: 'mapbox://styles/mapbox/streets-v11',
        center: [39.290843,8.562869],  // Update center here,
        zoom: 15
    }});

    var startMarker = new mapboxgl.Marker({{color: 'green'}});
    var endMarker = new mapboxgl.Marker({{color: 'red'}});
    var carMarker = new mapboxgl.Marker({{color: '#78aeed'}});
    var carPathCoordinates = [];
    
     map.on('load', function() {{
        startMarker.setLngLat([39.290273, 8.560654]).addTo(map);
    }});
    
    map.on('click', function(e) {{
        window.pyObj.mapClicked(e.lngLat.lng, e.lngLat.lat);
    }});

    new QWebChannel(qt.webChannelTransport, function (channel) {{
        window.pyObj = channel.objects.pyObj;
    }});

    function updateMarker(longitude, latitude) {{
        carMarker.setLngLat([longitude, latitude]).addTo(map);

        carPathCoordinates.push([longitude, latitude]);
        drawCarPath();
    }}

    function drawCarPath() {{
        if (map.getSource('carPath')) {{
            map.removeLayer('carPath');
            map.removeSource('carPath');
        }}

        map.addSource('carPath', {{
            'type': 'geojson',
            'data': {{
                'type': 'Feature',
                'properties': {{}},
                'geometry': {{
                    'type': 'LineString',
                    'coordinates': carPathCoordinates
                }}
            }}
        }});

        map.addLayer({{
            'id': 'carPath',
            'type': 'line',
            'source': 'carPath',
            'layout': {{
                'line-join': 'round',
                'line-cap': 'round'
            }},
            'paint': {{
                'line-color': 'white',
                'line-width': 3
            }}
        }});
    }}

    function setStart(longitude, latitude) {{
        startMarker.setLngLat([longitude, latitude]).addTo(map);
    }}

    function setEnd(longitude, latitude) {{
        endMarker.setLngLat([longitude, latitude]).addTo(map);
    }}

    function setRoute(coordinates) {{
        if (map.getSource('route')) {{
            map.removeLayer('route');
            map.removeSource('route');
        }}

        map.addSource('route', {{
            'type': 'geojson',
            'data': {{
                'type': 'Feature',
                'properties': {{}},
                'geometry': {{
                    'type': 'LineString',
                    'coordinates': coordinates
                }}
            }}
        }});

        map.addLayer({{
            'id': 'route',
            'type': 'line',
            'source': 'route',
            'layout': {{
                'line-join': 'round',
                'line-cap': 'round'
            }},
            'paint': {{
                'line-color': 'blue',
                'line-width': 6
            }}
        }});
    }}
</script>
</body>
</html>

""".format(mapbox_token, start_coordinates)



class MapboxApp(QObject):
    def __init__(self):
        super().__init__()
       
        self.view = QWebEngineView()
        self.view.setHtml(html)

        self.channel = QWebChannel()
        self.channel.registerObject("pyObj", self)
        self.view.page().setWebChannel(self.channel)
        self.view.resize(1200, 800)  # Set your desired size

        self.start = None  # Set the starting point
        self.end = None
        self.route = None,
        self.manuever = []
        self.current = None


        # Initialize the carTimer
        self.carTimer = QTimer()
        self.carTimer.timeout.connect(self.moveCarAlongRoute)


    @pyqtSlot(float, float)
    def mapClicked(self, longitude, latitude):
        if not self.start:
            self.start = [longitude, latitude]
            self.view.page().runJavaScript("setStart(%f, %f)" % (longitude, latitude))
            print(longitude,latitude)
        elif not self.end:
            self.end = [longitude, latitude]
            self.view.page().runJavaScript("setEnd(%f, %f)" % (longitude, latitude))
            self.calculateAndSetRoute()


    def get_maneuver(self, step):
        """
        Function to parse the maneuver from a given step.
        """
        # Extract the maneuver from the step
        maneuver = step['maneuver']

        # Extract the relevant information from the maneuver
        instruction = maneuver['instruction']
        typee = maneuver['type']
        modifier = maneuver.get('modifier', '')
        location = maneuver['location']
       
        # Return the parsed maneuver
        return (instruction,typee,modifier,location)
        
    


    def calculateAndSetRoute(self):
        # Call Mapbox Directions API to get a route
        source = ",".join(map(str, self.start))
        destination = ",".join(map(str, self.end))
        
        # Call Mapbox Directions API to get a route
        response = requests.get(
            f"https://api.mapbox.com/directions/v5/mapbox/driving/{source}%3B{destination}?alternatives=false&geometries=geojson&language=en&overview=full&steps=true&max_width=0.9&max_weight=0.5&access_token={os.getenv('private')}"
        )
        data = response.json()

        # Check if 'routes' in data
        if 'routes' in data and data['routes']:
            # Here we change the way we get the route information. 
            # Instead of taking the geometry directly, we iterate over the steps of the route
            # Each step has a geometry, which we use directly and add to the route
            self.route = []
            for leg in data['routes'][0]['legs']:
                for step in leg['steps']:
                    # use each step's geometry and add to the route
                    step_geometry = step['geometry']['coordinates']
                    self.route.extend(step_geometry)

                    maneuver = self.get_maneuver(step)
                    self.manuever.append(maneuver)
                    # print(self.manuever)
            
            self.view.page().runJavaScript("setRoute(%s)" % json.dumps(self.route))
            # start the carTimer
            self.carTimer.start(500)


    def moveCarAlongRoute(self):
            # Stop the QTimer if we've reached the end of the route
            if not self.route:
                self.carTimer.stop()
                return

            # Get the next coordinate
            coord = self.route.pop(0)
            for item in self.manuever:
                if coord == item[-1]:
                    car_loc = (item[0],item[1],item[-1])
                    if car_loc!=self.current:
                        self.current = car_loc
                        # display self.current in the pyqt widget 
                        print(self.current)

            # Move the car to the next coordinate
            self.view.page().runJavaScript("updateMarker(%f, %f)" % (coord[0], coord[1]))

            # Calculate the time to the next coordinate based on distance and speed
            if self.route:
                next_coord = self.route[0]
                dist = distance.distance(coord, next_coord).km
                speed = 50  # Assume a speed of 50 km/h, adjust as necessary
                time_to_next_coord = (dist / speed) * 3600  # in seconds

                # Set the QTimer interval to the time to the next coordinate
                self.carTimer.setInterval(round(time_to_next_coord * 500))  # QTimer works with milliseconds



if __name__ == "__main__":
    app = QApplication(sys.argv)
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

    mapboxApp = MapboxApp()
    mapboxApp.view.show()

    mapboxApp.mapClicked(start_coordinates[0],start_coordinates[-1])

    sys.exit(app.exec_())
