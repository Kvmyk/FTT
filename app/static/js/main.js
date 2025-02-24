// Dodaj globalne zmienne na górze pliku
let watchId = null;
let lastPosition = null;
const MIN_DISTANCE = 10; // minimalna odległość w metrach do wywołania aktualizacji
const UPDATE_INTERVAL = 30000; // 30 sekund
let lastSelectedTarget = null; // Add global variable to store last selected target

function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3; // promień Ziemi w metrach
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

function startIntelligentTracking() {
    if (!navigator.geolocation) {
        console.error('Geolokalizacja nie jest wspierana przez tę przeglądarkę.');
        return;
    }

    // Zatrzymaj poprzednie śledzenie jeśli istnieje
    stopIntelligentTracking();

    watchId = navigator.geolocation.watchPosition(
        (position) => {
            const currentPosition = {
                lat: position.coords.latitude,
                lon: position.coords.longitude
            };

            // Sprawdź czy jest to pierwsza pozycja lub czy użytkownik przemieścił się znacząco
            if (!lastPosition || calculateDistance(
                lastPosition.lat, lastPosition.lon,
                currentPosition.lat, currentPosition.lon
            ) > MIN_DISTANCE) {
                lastPosition = currentPosition;
                
                // Wyślij nową pozycję przez AJAX
                fetch('/location', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(currentPosition)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        return fetch('/render_map');
                    }
                })
                .then(response => response.text())
                .then(html => {
                    document.getElementById('map').innerHTML = html;
                    // Update the route info instead of nearest toilet distance
                    return fetch('/navigate_toilet_distance', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            user_lat: currentPosition.lat,
                            user_lon: currentPosition.lon,
                            target_lat: parseFloat(lastSelectedTarget?.lat || 0),
                            target_lon: parseFloat(lastSelectedTarget?.lon || 0)
                        })
                    });
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const nearestPinInfo = document.getElementById('nearestPinInfo');
                        const nearestPinText = document.getElementById('nearestPinText');
                        nearestPinText.innerText = `Od twojej lokalizacji do toalety jest ${data.distance} - ${data.name}.\nSzacowany czas dotarcia: ${data.duration} min 🚶`;
                        nearestPinInfo.classList.add('show');
                    }
                })
                .catch(error => console.error('Error:', error));
            }
        },
        (error) => console.error('Error:', error),
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: UPDATE_INTERVAL
        }
    );
}

function stopIntelligentTracking() {
    if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
        lastPosition = null;
    }
}


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
        // Instead of reloading, update the map dynamically
        return fetch('/render_map');
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('map').innerHTML = html;
        document.getElementById('loadingOverlay').style.display = 'none';
        // Now that the user location is set, call nearest_toilet_distance
        return fetch('/nearest_toilet_distance');
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const nearestPinInfo = document.getElementById('nearestPinInfo');
            const nearestPinText = document.getElementById('nearestPinText');
            nearestPinText.innerText = `Od twojej lokalizacji do najbliższej toalety jest ${data.distance} - ${data.name}.\nSzacowany czas dotarcia: ${data.duration} min 🚶`;
            nearestPinInfo.classList.add('show');
        }
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
    // Dodaj obsługę przełącznika śledzenia
    const trackingToggle = document.getElementById('locationTrackingToggle');
    trackingToggle.addEventListener('change', function() {
        if (this.checked) {
            startIntelligentTracking();
        } else {
            stopIntelligentTracking();
        }
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

function checkProfanity(text) {
    return fetch('/check_profanity', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text })
    })
    .then(response => response.json());
}

function submitModal() {
    const description = document.getElementById('descriptionInput').value;

    checkProfanity(description).then(data => {
        if (data.status === 'hate') {
            alert('Opis zawiera mowę nienawiści i nie może zostać dodany.');
            return;
        }

        // Kontynuuj dodawanie pina, jeśli opis jest neutralny
        const useUserLocation = document.getElementById('useUserLocation').checked;
        const userInput = document.getElementById('userInput').value;
        const payable = document.getElementById('paidInput').checked;
        const onlyForClients = document.getElementById('customersOnlyInput').checked;
        const forDisabled = document.getElementById('disabilityInput').checked;
        const rating = document.getElementById('ratingInput').value;
        const photoInput = document.getElementById('photoInput').files;
        const formData = new FormData();

        formData.append('userInput', userInput);
        formData.append('description', description);
        formData.append('payable', payable);
        formData.append('onlyForClients', onlyForClients);
        formData.append('forDisabled', forDisabled);
        formData.append('rating', rating);
        formData.append('useUserLocation', useUserLocation);

        for (let i = 0; i < photoInput.length; i++) {
            formData.append('photos', photoInput[i]);
        }

        fetch('/submit', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById('myModal').style.display = 'none';
                window.location.reload();
            } else {
                console.error('Error:', data.message);
            }
        });
    });
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
    const comment = document.getElementById('commentText').value;
    const rating = document.getElementById('commentRating').value;

    if (!comment || !rating) {
        alert('Wszystkie pola muszą być wypełnione.');
        return;
    }

    if (!validateCommentRating()) {
        return;
    }

    checkProfanity(comment).then(data => {
        if (data.status === 'hate') {
            alert('Komentarz zawiera mowę nienawiści i nie może zostać dodany.');
            return;
        }

        const lat = document.getElementById('commentModal').dataset.lat;
        const lon = document.getElementById('commentModal').dataset.lon;

        const formData = new FormData();
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

function isInOpoleProvince(lat, lon) {
    // Granice województwa opolskiego (przybliżone)
    const opoleBounds = {
        north: 51.0,
        south: 49.5,
        west: 16.5,
        east: 18.5
    };

    return lat >= opoleBounds.south && lat <= opoleBounds.north &&
           lon >= opoleBounds.west && lon <= opoleBounds.east;
}

function navigateToToilet(targetLat, targetLon) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLat = position.coords.latitude;
                const userLon = position.coords.longitude;

                if (!isInOpoleProvince(userLat, userLon)) {
                    alert('Znajdujesz się poza województwem opolskim. Nawigacja jest dostępna tylko w województwie opolskim.');
                    return;
                }

                if (!isInOpoleProvince(targetLat, targetLon)) {
                    alert('Marker znajduje się poza województwem opolskim. Nawigacja jest dostępna tylko do markerów w województwie opolskim.');
                    return;
                }

                // Store the selected target
                lastSelectedTarget = {
                    lat: targetLat,
                    lon: targetLon
                };

                fetch('/navigate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        target_lat: targetLat,
                        target_lon: targetLon
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // After successful navigation, update the tracking state
                        const trackingToggle = document.getElementById('locationTrackingToggle');
                        if (trackingToggle.checked) {
                            // Restart tracking with new target
                            stopIntelligentTracking();
                            startIntelligentTracking();
                        }
                        return fetch('/render_map');
                    }
                })
                .then(response => response.text())
                .then(html => {
                    document.getElementById('map').innerHTML = html;
                    return fetch('/navigate_toilet_distance', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            user_lat: userLat,
                            user_lon: userLon,
                            target_lat: parseFloat(targetLat),
                            target_lon: parseFloat(targetLon)
                        })
                    });
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const nearestPinInfo = document.getElementById('nearestPinInfo');
                        const nearestPinText = document.getElementById('nearestPinText');
                        nearestPinText.innerText = `Od twojej lokalizacji do toalety jest ${data.distance} – ${data.name}.\nSzacowany czas dotarcia: ${data.duration} min 🚶`;
                        nearestPinInfo.classList.add('show');
                    }
                })
                .catch(error => console.error('Error:', error));
            }
        );
    }
}

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

document.addEventListener('DOMContentLoaded', function() {
    // Obsługa przycisku filtrów
    document.querySelector('.filter-button').addEventListener('click', function() {
        document.getElementById('filterModal').style.display = 'block';
    });
    document.getElementById('closeFilterModal').addEventListener('click', function() {
        document.getElementById('filterModal').style.display = 'none';
    });
});

function applyFilters() {
    const filterRating = document.getElementById('filterRating').value;
    const rating = parseInt(filterRating, 10) || 0; // Dodaj domyślną wartość 0

    // Zmień warunek, aby akceptował 0 jako brak filtra
    if (rating < 0 || rating > 10) {
        alert('Ocena musi być w zakresie od 0 do 10.');
        return;
    }

    fetch('/apply_filters', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filterPayable: document.getElementById('filterPayable').checked,
            filterForClients: document.getElementById('filterForClients').checked,
            filterForDisabled: document.getElementById('filterForDisabled').checked,
            filterRating: rating
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('filterModal').style.display = 'none';
            // Zamiast pełnego przeładowania strony, zaktualizuj mapę dynamicznie
            fetch('/render_map')
                .then(response => response.text())
                .then(html => {
                    document.getElementById('map').innerHTML = html;
                });
        } else {
            console.error('Error:', data.message);
        }
    });
}

function showAllToilets() {
    // Wyczyść wszystkie filtry
    document.getElementById('filterPayable').checked = false;
    document.getElementById('filterForClients').checked = false;
    document.getElementById('filterForDisabled').checked = false;

    // Wyślij żądanie do serwera, aby przywrócić wszystkie markery
    fetch('/apply_filters', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filterPayable: false,
            filterForClients: false,
            filterForDisabled: false
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('filterModal').style.display = 'none';
            window.location.reload();
        } else {
            console.error('Error:', data.message);
        }
    });
}

function resizeImage(file, maxWidth, maxHeight, callback) {
    const reader = new FileReader();
    reader.onload = function(event) {
        const img = new Image();
        img.onload = function() {
            let width = img.width;
            let height = img.height;

            if (width > height) {
                if (width > maxWidth) {
                    height *= maxWidth / width;
                    width = maxWidth;
                }
            } else {
                if (height > maxHeight) {
                    width *= maxHeight / height;
                    height = maxHeight;
                }
            }

            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            canvas.toBlob(callback, file.type, 0.8);
        }
        img.src = event.target.result;
    }
    reader.readAsDataURL(file);
}

document.getElementById('photoInput').addEventListener('change', function(e) {
    const container = document.getElementById('imagePreviewContainer');
    container.innerHTML = '';

    const files = Array.from(this.files);
    const validFiles = files.filter(file => {
        const validTypes = ['image/jpeg', 'image/png'];
        if (!validTypes.includes(file.type)) {
            alert('Dozwolone są tylko pliki PNG i JPG.');
            return false;
        }
        return true;
    });

    if (validFiles.length === 0) {
        this.value = ''; // Clear the input if no valid files
        return;
    }

    validFiles.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(event) {
            const img = document.createElement('img');
            img.src = event.target.result;
            img.className = 'imagePreview';
            container.appendChild(img);
        }
        reader.readAsDataURL(file);
    });

    this.files = new FileList(...validFiles);
});
