function getLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(sendPosition, showError, { enableHighAccuracy: true });
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}

function sendPosition(position) {
    localStorage.setItem('lat', position.coords.latitude);
    localStorage.setItem('lon', position.coords.longitude);

    fetch('/location', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            lat: position.coords.latitude,
            lon: position.coords.longitude
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
        localStorage.setItem('locationUpdated', 'true');
        window.location.reload();
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}

function showError(error) {
    switch(error.code) {
        case error.PERMISSION_DENIED:
            alert("User denied the request for Geolocation.");
            break;
        case error.POSITION_UNAVAILABLE:
            alert("Location information is unavailable.");
            break;
        case error.TIMEOUT:
            alert("The request to get user location timed out.");
            break;
        case error.UNKNOWN_ERROR:
            alert("An unknown error occurred.");
            break;
    }
}

function updateMapWithStoredLocation() {
    const lat = localStorage.getItem('lat');
    const lon = localStorage.getItem('lon');
    if (lat && lon) {
        fetch('/location', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                lat: parseFloat(lat),
                lon: parseFloat(lon)
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data);
            localStorage.setItem('locationUpdated', 'true');
            window.location.reload();
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    }
}

function initMap() {
    // Inicjalizuj mapę na domyślnych współrzędnych
    var map = L.map('map').setView([52.2297, 21.0122], 15);

    // Dodaj warstwę mapy (tiles)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap contributors © CARTO',
        maxZoom: 18,
        minZoom: 2
    }).addTo(map);

    // Pobierz i dodaj markery z serwera
    fetch('/get_markers')
        .then(response => response.json())
        .then(data => {
            data.markers.forEach(function(marker) {
                var popupContent = `
                    <div style="width: 300px;">
                        <h2 style="font-size: 1.5em;">${marker.name}</h2>
                        <p style="font-size: 1em;">${marker.description}</p>
                        <p><strong>Płatna:</strong> ${marker.payable ? 'TAK' : 'NIE'}</p>
                        <p><strong>Tylko dla klientów:</strong> ${marker.onlyForClients ? 'TAK' : 'NIE'}</p>
                        <p><strong>Ocena:</strong> ${marker.rating || 'Brak oceny'}</p>
                        ${marker.photo ? `<img src="data:image/png;base64,${marker.photo}" style="width: 100%; height: auto;">` : ''}
                    </div>
                `;

                var toiletIcon = L.icon({
                    iconUrl: 'static/img/toilet_icon.png', // Ścieżka do pliku toilet_icon.png
                    iconSize: [50, 50]
                });

                L.marker([marker.lat, marker.lon], {icon: toiletIcon})
                    .bindPopup(popupContent)
                    .addTo(map);
            });
        })
        .catch(error => console.error('Error:', error));

    // Pobierz lokalizację użytkownika
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            var userLat = position.coords.latitude;
            var userLon = position.coords.longitude;

            // Dodaj marker lokalizacji użytkownika
            var userMarker = L.marker([userLat, userLon], {icon: L.AwesomeMarkers.icon({
                icon: 'user',
                markerColor: 'red',
                prefix: 'fa'
            })}).addTo(map);
            userMarker.bindPopup("Twoja lokalizacja").openPopup();

            // Centruj mapę na lokalizacji użytkownika
            map.setView([userLat, userLon], 15);

            // Pobierz trasę i dodaj ją na mapie
            fetch('/get_route', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({lat: userLat, lon: userLon})
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    var routeCoordinates = data.route.map(function(coord) {
                        return [coord[1], coord[0]]; // Zamień na [lat, lon]
                    });

                    // Dodaj linię trasy na mapę
                    var routeLine = L.polyline(routeCoordinates, {
                        color: 'red',
                        weight: 5,
                        opacity: 0.7
                    }).addTo(map);

                    // Dodaj znacznik z długością trasy w połowie linii
                    var midPointIndex = Math.floor(routeCoordinates.length / 2);
                    var midPoint = routeCoordinates[midPointIndex];

                    var distanceMarker = L.marker(midPoint, {
                        icon: L.divIcon({
                            html: `<div style="font-size: 12px; color: red; width: 100px;">${data.distance}</div>`,
                            className: ''
                        })
                    }).addTo(map);

                    // Wyświetl informacje o najbliższym punkcie
                    const nearestPinInfo = document.getElementById('nearestPinInfo');
                    const nearestPinText = document.getElementById('nearestPinText');
                    nearestPinText.innerText = `Od twojej lokalizacji do najbliższej toalety jest ${data.distance} - ${data.name}`;
                    nearestPinInfo.style.display = 'block';
                }
            })
            .catch(error => console.error('Error:', error));
        }, function(error) {
            console.error("Błąd podczas pobierania lokalizacji użytkownika:", error);
        });
    } else {
        alert("Geolokalizacja nie jest obsługiwana przez tę przeglądarkę.");
    }

    // Obsługa zdarzeń dla przycisku circle-plus
    document.querySelector('.circle-plus').addEventListener('click', function() {
        document.getElementById('myModal').style.display = 'block';
    });

    document.getElementById('closeModal').addEventListener('click', function() {
        document.getElementById('myModal').style.display = 'none';
    });

    // Pokaż blok, gdy użytkownik najedzie kursorem na trasę
    document.addEventListener('mouseover', function(event) {
        if (event.target.tagName === 'path') { // Zakładając, że trasa jest rysowana jako element <path>
            const nearestPinInfo = document.getElementById('nearestPinInfo');
            nearestPinInfo.classList.remove('hide');
            nearestPinInfo.classList.add('show');
        }
    });

    // Ukryj blok, gdy użytkownik opuści trasę
    document.addEventListener('mouseout', function(event) {
        if (event.target.tagName === 'path') { // Zakładając, że trasa jest rysowana jako element <path>
            const nearestPinInfo = document.getElementById('nearestPinInfo');
            nearestPinInfo.classList.remove('show');
            nearestPinInfo.classList.add('hide');
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initMap();
});

function submitModal() {
    var userInput = document.getElementById('userInput').value;
    var descriptionInput = document.getElementById('descriptionInput').value;
    var ratingInput = document.getElementById('ratingInput').value;
    var paidInput = document.getElementById('paidInput').checked;
    var customersOnlyInput = document.getElementById('customersOnlyInput').checked;
    var photoInput = document.getElementById('photoInput').files;

    var formData = new FormData();
    formData.append('userInput', userInput);
    formData.append('description', descriptionInput);
    formData.append('rating', ratingInput);
    formData.append('payable', paidInput);
    formData.append('onlyForClients', customersOnlyInput);
    for (var i = 0; i < photoInput.length; i++) {
        formData.append('photos', photoInput[i]);
    }

    fetch('/submit', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
        if (data.status === 'success') {
            document.getElementById('myModal').style.display = 'none';
            window.location.reload();
        }
    })
    .catch(error => console.error('Error:', error));
}