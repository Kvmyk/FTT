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
        // Zamiast przeładowywać stronę, pobierz i zaktualizuj mapę
        return fetch('/render_map');
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('map').innerHTML = html;
        document.getElementById('loadingOverlay').style.display = 'none';
        initializeRouteHoverEffects(); // Add this line
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
            // Zamiast reload, załaduj mapę dynamicznie
            fetch('/render_map')
                .then(response => response.text())
                .then(html => {
                    document.getElementById('map').innerHTML = html;
                })
                .catch(error => console.error('Error loading map:', error));
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Usuwanie zapisanej lokalizacji
    localStorage.removeItem('lat');
    localStorage.removeItem('lon');
    localStorage.removeItem('locationUpdated');

    getLocation();

    document.querySelector('.circle-plus').addEventListener('click', function() {
        document.getElementById('myModal').style.display = 'block';
    });
    document.getElementById('closeModal').addEventListener('click', function() {
        document.getElementById('myModal').style.display = 'none';
    });

    document.getElementById('closeCommentModal').addEventListener('click', function() {
        document.getElementById('commentModal').style.display = 'none';
    });
});

function validateRating() {
    const ratingInput = document.getElementById('ratingInput');
    const rating = parseInt(ratingInput.value, 10);
    if (rating < 1 || rating > 10) {
        alert('Ocena musi być w zakresie od 1 do 10.');
        return false;
    }
    return true;
}

function validateCommentRating() {
    const ratingInput = document.getElementById('commentRating');
    const rating = parseInt(ratingInput.value, 10);
    if (rating < 1 || rating > 10) {
        alert('Ocena musi być w zakresie od 1 do 10.');
        return false;
    }
    return true;
}


function submitModal() {
    var userInput = document.getElementById('userInput').value;
    var descriptionInput = document.getElementById('descriptionInput').value;
    var ratingInput = document.getElementById('ratingInput').value;

    if (!userInput || !descriptionInput || !ratingInput) {
        alert('Wszystkie pola muszą być wypełnione.');
        return;
    }

    if (!validateRating()) {
        return;
    }

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

function openCommentModal(lat, lon) {
    document.getElementById('commentModal').style.display = 'block';
    document.getElementById('commentModal').dataset.lat = lat;
    document.getElementById('commentModal').dataset.lon = lon;
}

window.openCommentModal = function(lat, lon) {
    document.getElementById('commentModal').style.display = 'block';
    document.getElementById('commentModal').dataset.lat = lat;
    document.getElementById('commentModal').dataset.lon = lon;
};

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('closeCommentModal').addEventListener('click', function() {
        document.getElementById('commentModal').style.display = 'none';
    });
});

function submitComment() {
    var comment = document.getElementById('commentText').value;
    var rating = document.getElementById('commentRating').value;
    if (!comment || !rating) {
        alert('Wszystkie pola muszą być wypełnione.');
        return;
    }

    if (!validateCommentRating()) {
        return;
    }

    var lat = document.getElementById('commentModal').dataset.lat;
    var lon = document.getElementById('commentModal').dataset.lon;

    
    var formData = new FormData();
    formData.append('lat', lat);
    formData.append('lon', lon);
    formData.append('comment', comment);
    formData.append('rating', rating);

    fetch('/add_comment', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('commentModal').style.display = 'none';
            window.location.reload();
        } else {
            console.error('Error:', data.message);
        }
    });
}
function animateRoute(map, coordinates) {
    let currentIndex = 0;
    let polyline = L.polyline([], { color: 'red', weight: 5 }).addTo(map);

    function drawSegment() {
      if (currentIndex < coordinates.length) {
        polyline.addLatLng(L.latLng(coordinates[currentIndex]));
        currentIndex++;
        requestAnimationFrame(drawSegment);
      }
    }
    drawSegment();
  }

window.navigateToToilet = function(targetLat, targetLon) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLat = position.coords.latitude;
                const userLon = position.coords.longitude;
                
                // Oblicz odległość używając funkcji haversine (dodaj tę funkcję)
                const distance = calculateDistance(userLat, userLon, targetLat, targetLon);
                const distanceKm = distance / 1000;

                if (distanceKm > 30000) {
                    alert('Nie możesz nawigować do tej toalety - znajduje się dalej niż w promieniu 3km od Twojej lokalizacji.');
                    return;
                }
                
                // Jeśli odległość jest OK, kontynuuj nawigację
                fetch('/navigate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        user_lat: userLat,
                        user_lon: userLon,
                        target_lat: targetLat,
                        target_lon: targetLon
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        fetch('/render_map')
                            .then(response => response.text())
                            .then(html => {
                                document.getElementById('map').innerHTML = html;
                            })
                            .catch(error => console.error('Error updating map:', error));
                    } else {
                        alert('Nie udało się wyznaczyć trasy');
                    }
                });
            },
            (error) => alert('Nie udało się pobrać lokalizacji: ' + error.message)
        );
    }
};

// Dodaj funkcję do obliczania odległości
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3; // Promień Ziemi w metrach
    const φ1 = lat1 * Math.PI/180;
    const φ2 = lat2 * Math.PI/180;
    const Δφ = (lat2-lat1) * Math.PI/180;
    const Δλ = (lon2-lon1) * Math.PI/180;

    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c; // w metrach
}

// Dodaj po załadowaniu mapy
document.addEventListener('DOMContentLoaded', function() {
    // Obsługa przycisków w popupach
    const buttons = document.querySelectorAll('.popup-button');
    buttons.forEach(button => {
        // Dodaj efekt ripple przy kliknięciu
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            ripple.className = 'ripple';
            
            button.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
});

function initializeRouteHoverEffects() {
    const paths = document.querySelectorAll('path');
    const nearestPinInfo = document.getElementById('nearestPinInfo');
    const nearestPinText = document.getElementById('nearestPinText');
    
    paths.forEach(path => {
        path.addEventListener('mouseover', () => {
            if (nearestPinInfo && path.classList.contains('path.leaflet-interactive')) {
                nearestPinInfo.classList.remove('hide');
                nearestPinInfo.classList.add('show');
            }
        });
        
        path.addEventListener('mouseout', () => {
            if (nearestPinInfo) {
                nearestPinInfo.classList.remove('show');
                nearestPinInfo.classList.add('hide');
            }
        });
    });
}
