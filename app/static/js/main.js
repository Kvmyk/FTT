// Dodaj globalne zmienne na górze pliku
let watchId = null;
let lastPosition = null;
const MIN_DISTANCE = 10; // minimalna odległość w metrach do wywołania aktualizacji
const UPDATE_INTERVAL = 30000; // 30 sekund

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

    stopIntelligentTracking();

    // Sprawdź czy cel nawigacji nadal istnieje po zastosowaniu filtrów
    const targetLat = localStorage.getItem('targetLat');
    const targetLon = localStorage.getItem('targetLon');
    
    // Zawsze wykonaj zapytanie do check_marker_exists
    fetch('/check_marker_exists', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            lat: targetLat ? parseFloat(targetLat) : null,
            lon: targetLon ? parseFloat(targetLon) : null,
            checkMode: targetLat && targetLon ? 'target' : 'init'
        })
    })
    .then(response => response.json())
    .then(data => {
        // Jeśli był cel i nie istnieje, usuń go
        if (targetLat && targetLon && !data.exists) {
            localStorage.removeItem('targetLat');
            localStorage.removeItem('targetLon');
            alert('Cel nawigacji został usunięty przez zastosowane filtry. Wybierz nowy cel.');
            // Po usunięciu celu, odśwież stronę aby zaktualizować mapę
            window.location.reload();
            return false;
        }
        return true;
    })
    .then(targetExists => {
        watchId = navigator.geolocation.watchPosition(
            (position) => {
                const currentPosition = {
                    lat: position.coords.latitude,
                    lon: position.coords.longitude
                };

                // Kontynuuj tylko jeśli cel istnieje lub nie ma celu
                if (!targetExists && (localStorage.getItem('targetLat') || localStorage.getItem('targetLon'))) {
                    return;
                }
                
                if (!isInOpoleProvince(currentPosition.lat, currentPosition.lon)) {
                    alert('Znajdujesz się poza województwem opolskim. Nawigacja jest dostępna tylko w województwie opolskim.');
                    stopIntelligentTracking();
                    return;
                }

                if (targetLat && targetLon && !isInOpoleProvince(parseFloat(targetLat), parseFloat(targetLon))) {
                    alert('Marker znajduje się poza województwem opolskim. Nawigacja jest dostępna tylko do markerów w województwie opolskim.');
                    stopIntelligentTracking();
                    return;
                }

                // Reszta logiki śledzenia...
                if (!lastPosition || calculateDistance(
                    lastPosition.lat, lastPosition.lon,
                    currentPosition.lat, currentPosition.lon
                ) > MIN_DISTANCE) {
                    lastPosition = currentPosition;
                        
                    // Zawsze sprawdzaj zapisany cel nawigacji
                    const targetLat = localStorage.getItem('targetLat');
                    const targetLon = localStorage.getItem('targetLon');
                    
                    // Use the new endpoint to update user location
                    fetch('/update_user_location', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            user_lat: currentPosition.lat,
                            user_lon: currentPosition.lon
                        })
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
                        
                        // After map is updated, get distance info if we have a target
                        if (targetLat && targetLon) {
                            return fetch('/navigate', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    user_lat: currentPosition.lat,
                                    user_lon: currentPosition.lon,
                                    target_lat: parseFloat(targetLat),
                                    target_lon: parseFloat(targetLon)
                                })
                            });
                        }
                        return null;
                    })
                    .then(response => response ? response.json() : null)
                    .then(data => {
                        if (data && data.status === 'success') {
                            const nearestPinInfo = document.getElementById('nearestPinInfo');
                            const nearestPinText = document.getElementById('nearestPinText');
                            nearestPinText.innerText = `Od twojej lokalizacji do toalety jest ${data.distance} – ${data.name}.\nSzacowany czas dotarcia: ${data.duration} min 🚶`;
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
    })
    .catch(error => console.error('Error:', error));
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
            localStorage.setItem('trackingEnabled', 'true');
            startIntelligentTracking();
        } else {
            localStorage.setItem('trackingEnabled', 'false');
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
    const userInput = document.getElementById('userInput').value;
    const rating = document.getElementById('ratingInput').value;

    // Check if required fields are filled
    if (!userInput || !description || !rating) {
        alert('Wszystkie pola (nazwa, opis i ocena) muszą być wypełnione.');
        return;
    }

    // Validate character limits
    if (userInput.length > 512) {
        alert('Nazwa toalety nie może przekraczać 512 znaków.');
        return;
    }

    if (description.length > 512) {
        alert('Opis toalety nie może przekraczać 512 znaków.');
        return;
    }

    // Validate rating
    if (!validateRating()) {
        return;
    }

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
        formData.append('weekday_open', document.getElementById('weekdayOpenTime').value);
        formData.append('weekday_close', document.getElementById('weekdayCloseTime').value);
        formData.append('weekend_open', document.getElementById('weekendOpenTime').value);
        formData.append('weekend_close', document.getElementById('weekendCloseTime').value);

        for (var i = 0; i < photoInput.length; i++) {
            var file = photoInput[i];
            if (file.size > 5 * 1024 * 1024) { // 5 MB limit
                alert('Rozmiar pliku nie może przekraczać 5 MB.');
                return;
            }
            if (!file.type.match('image/jpeg') && !file.type.match('image/png')) {
                alert('Dozwolone są tylko pliki w formacie .jpg i .png.');
                return;
            }
            formData.append('photos', file);
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

    // Check comment length
    if (comment.length > 512) {
        alert('Komentarz nie może przekraczać 512 znaków.');
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
    // Zapisz nowy cel w localStorage
    localStorage.setItem('targetLat', targetLat);
    localStorage.setItem('targetLon', targetLon);

    // Jeśli śledzenie jest włączone, zrestartuj je z nowym celem
    const trackingEnabled = document.getElementById('locationTrackingToggle').checked;
    if (trackingEnabled) {
        // If tracking is enabled, just restart tracking
        stopIntelligentTracking();
        startIntelligentTracking();
    }


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
                    if (trackingEnabled) {
                        // If tracking is enabled, just restart tracking
                        stopIntelligentTracking();
                        startIntelligentTracking();
                    } else {
                        // Continue with the rest of the navigation logic
                        if (data.status === 'success') {
                            return fetch('/render_map');
                        }
                    }
                })
                .then(response => response && !trackingEnabled ? response.text() : null)
                .then(html => {
                    if (html) {
                        document.getElementById('map').innerHTML = html;
                        // Dodatkowy fetch do /navigate_toilet_distance
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
                    }
                    return null;
                })
                .then(response => response ? response.json() : null)
                .then(data => {
                    if (data && data.status === 'success') {
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
    const rating = parseInt(filterRating, 10);

    if (rating < 1 || rating > 10) {
        alert('Ocena musi być w zakresie od 1 do 10.');
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
            
            // Zamiast restartowania śledzenia, odświeżamy stronę
            window.location.reload();
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
    container.innerHTML = ''; // Clear previous previews
    
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB in bytes
    const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/jpg'];
    
    const files = Array.from(this.files);
    const resizedFiles = [];
    let hasInvalidFiles = false;

    files.forEach(file => {
        // Check file type
        if (!ALLOWED_TYPES.includes(file.type)) {
            alert(`Plik "${file.name}" ma nieprawidłowy format. Dozwolone formaty to: PNG, JPG`);
            hasInvalidFiles = true;
            return;
        }

        // Check file size
        if (file.size > MAX_FILE_SIZE) {
            alert(`Plik "${file.name}" jest za duży. Maksymalny rozmiar to 5MB`);
            hasInvalidFiles = true;
            return;
        }

        // If file passes validation, proceed with resizing
        resizeImage(file, 800, 800, function(resizedBlob) {
            resizedFiles.push(resizedBlob);
            const reader = new FileReader();
            reader.onload = function(event) {
                const img = document.createElement('img');
                img.src = event.target.result;
                img.className = 'imagePreview';
                container.appendChild(img);
            }
            reader.readAsDataURL(resizedBlob);
        });
    });

    // Clear input if any file failed validation
    if (hasInvalidFiles) {
        this.value = '';
        container.innerHTML = '';
    }
});
