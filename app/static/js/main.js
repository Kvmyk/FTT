// Dodaj globalne zmienne na górze pliku
let watchId = null;
let lastPosition = null;
let forceNextUpdate = false; // flaga wymuszająca natychmiastową aktualizację
const MIN_DISTANCE = 25; // minimalna odległość w metrach do wywołania aktualizacji
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

                // Reszta logiki śledzenia...
                if (!lastPosition || forceNextUpdate || calculateDistance(
                    lastPosition.lat, lastPosition.lon,
                    currentPosition.lat, currentPosition.lon
                ) > MIN_DISTANCE) {
                    lastPosition = currentPosition;
                    forceNextUpdate = false; // Resetuj flagę po wymuszeniu aktualizacji
                        
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
                            user_lon: currentPosition.lon,
                            target_lat: targetLat ? parseFloat(targetLat) : null,
                            target_lon: targetLon ? parseFloat(targetLon) : null
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            // Jeśli serwer zwrócił informacje o trasie
                            if (data.distance && data.duration && data.name) {
                                const nearestPinInfo = document.getElementById('nearestPinInfo');
                                const nearestPinText = document.getElementById('nearestPinText');
                                const cancelBtn = document.getElementById('cancelNavigationBtn');
                                
                                // Użyj flagi is_nearest z serwera do rozróżnienia typu nawigacji
                                console.log('updateUserLocation response:', {
                                    is_nearest: data.is_nearest,
                                    name: data.name,
                                    hasTarget: localStorage.getItem('targetLat') && localStorage.getItem('targetLon')
                                });
                                
                                if (data.is_nearest) {
                                    // Najbliższa toaleta - NIE pokazuj przycisku anulowania
                                    nearestPinText.innerText = `Od twojej lokalizacji do najbliższej toalety jest ${data.distance} - ${data.name}.\nSzacowany czas dotarcia: ${data.duration} min 🚶`;
                                    cancelBtn.style.display = 'none';
                                    console.log('Set cancel button to none (nearest toilet)');
                                } else {
                                    // Nawigacja do konkretnego celu - pokaż przycisk anulowania
                                    nearestPinText.innerText = `Nawigacja do: ${data.name}\nOdległość: ${data.distance}\nSzacowany czas: ${data.duration} min 🚶`;
                                    cancelBtn.style.display = 'inline-block';
                                    console.log('Set cancel button to inline-block (target navigation)');
                                }
                                
                                nearestPinInfo.classList.add('show');
                            }
                            return fetch('/render_map');
                        }
                    })
                    .then(response => response.text())
                    .then(html => {
                        document.getElementById('map').innerHTML = html;
                    })
                    .catch(error => {
                        console.error('Error:', error);
                    });
                }
            },
            (error) => {
                console.error('Error:', error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: UPDATE_INTERVAL
            }
        );
    })
    .catch(error => {
        console.error('Error:', error);
    });
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
        
        // Sprawdź czy jest aktywny cel nawigacji
        const targetLat = localStorage.getItem('targetLat');
        const targetLon = localStorage.getItem('targetLon');
        
        if (targetLat && targetLon) {
            // Jeśli jest cel nawigacji, pokaż informacje o nim
            return fetch('/navigate_toilet_distance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_lat: position.coords.latitude,
                    user_lon: position.coords.longitude,
                    target_lat: parseFloat(targetLat),
                    target_lon: parseFloat(targetLon)
                })
            });
        } else {
            // Jeśli nie ma celu nawigacji, pokaż najbliższą toaletę
            return fetch('/nearest_toilet_distance');
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const nearestPinInfo = document.getElementById('nearestPinInfo');
            const nearestPinText = document.getElementById('nearestPinText');
            const cancelBtn = document.getElementById('cancelNavigationBtn');
            const targetLat = localStorage.getItem('targetLat');
            const targetLon = localStorage.getItem('targetLon');
            
            if (targetLat && targetLon) {
                // Nawigacja do konkretnego celu
                nearestPinText.innerText = `Nawigacja do: ${data.name}\nOdległość: ${data.distance}\nSzacowany czas: ${data.duration} min 🚶`;
                cancelBtn.style.display = 'inline-block';
            } else {
                // Najbliższa toaleta
                nearestPinText.innerText = `Od twojej lokalizacji do najbliższej toalety jest ${data.distance} - ${data.name}.\nSzacowany czas dotarcia: ${data.duration} min 🚶`;
                cancelBtn.style.display = 'none';
            }
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
    const placeName = document.getElementById('placeNameInput').value;
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

    document.getElementById('myModal').style.display = 'none';

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
        formData.append('place_name', placeName);
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
                alert('Error: ' + data.message);
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

    document.getElementById('commentModal').style.display = 'none';


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

function navigateToToilet(targetLat, targetLon) {
    // Zapisz nowy cel w localStorage
    localStorage.setItem('targetLat', targetLat);
    localStorage.setItem('targetLon', targetLon);
    
    // Wymusz natychmiastową aktualizację przy następnym śledzeniu
    forceNextUpdate = true;
    
    // Tymczasowo zatrzymaj śledzenie podczas ustawiania nowego celu
    const trackingEnabled = document.getElementById('locationTrackingToggle')?.checked;
    if (trackingEnabled) {
        stopIntelligentTracking();
    }

    // Zawsze generuj trasę natychmiast, niezależnie od trybu śledzenia
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLat = position.coords.latitude;
                const userLon = position.coords.longitude;

                // Użyj tego samego endpointu co inteligentne śledzenie dla spójności
                fetch('/update_user_location', {
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
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Jeśli serwer zwrócił informacje o trasie, pokaż je
                        if (data.distance && data.duration && data.name) {
                            const nearestPinInfo = document.getElementById('nearestPinInfo');
                            const nearestPinText = document.getElementById('nearestPinText');
                            const cancelBtn = document.getElementById('cancelNavigationBtn');
                            nearestPinText.innerText = `Nawigacja do: ${data.name}\nOdległość: ${data.distance}\nSzacowany czas: ${data.duration} min 🚶`;
                            nearestPinInfo.classList.add('show');
                            cancelBtn.style.display = 'inline-block';
                        }
                        
                        return fetch('/render_map');
                    }
                })
                .then(response => response ? response.text() : null)
                .then(html => {
                    if (html) {
                        document.getElementById('map').innerHTML = html;
                        
                        // Restart śledzenia jeśli było włączone (z opóźnieniem dla stabilności)
                        if (trackingEnabled) {
                            setTimeout(() => {
                                startIntelligentTracking();
                            }, 500); // 500ms opóźnienie
                        }
                    }
                })
                .catch(error => console.error('Error:', error));
            },
            (error) => {
                console.error('Error getting location:', error);
                // Restart śledzenia nawet w przypadku błędu
                if (trackingEnabled) {
                    setTimeout(() => {
                        startIntelligentTracking();
                    }, 500);
                }
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

// Dodaj po załadowaniu mapy
document.addEventListener('DOMContentLoaded', function() {
    // Istniejący kod...
    
    // Dodaj nową funkcję naprawiającą problemy z klikaniem po odświeżeniu
    function resetMapInteractions() {
        const mapElement = document.getElementById('map');
        const mapContainer = document.querySelector('.leaflet-container');
        
        if (mapContainer) {
            // Usuń i ponownie dodaj nasłuchiwacz zdarzeń dotknięcia
            mapContainer.style.touchAction = 'none';
            setTimeout(() => {
                mapContainer.style.touchAction = 'auto';
            }, 100);
            
            // Wymuś odświeżenie wskaźników zdarzeń
            const allClickableElements = document.querySelectorAll('.circle-plus, .filter-button, #nearestPinInfo, .location-tracking-toggle, .popup-button, button, input[type="checkbox"]');
            allClickableElements.forEach(el => {
                el.style.pointerEvents = 'none';
                setTimeout(() => {
                    el.style.pointerEvents = 'auto';
                }, 50);
            });
        }
    }
    
    // Wywołaj po każdym odświeżeniu mapy
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const result = originalFetch.apply(this, args);
        if (args[0].includes('/render_map')) {
            result.then(() => {
                setTimeout(resetMapInteractions, 300);
            });
        }
        return result;
    };
});

// Dodaj po załadowaniu mapy
document.addEventListener('DOMContentLoaded', function() {
    // Istniejący kod...
    
    // Ulepszona funkcja naprawiająca problemy z interakcjami
    function resetMapInteractions() {
        const mapElement = document.getElementById('map');
        const mapContainer = document.querySelector('.leaflet-container');
        const leafletObjects = document.querySelectorAll('.leaflet-interactive');
        
        if (mapContainer) {
            // Bardziej agresywne resetowanie właściwości dotknięć
            mapContainer.style.touchAction = 'none';
            document.body.style.touchAction = 'auto';
            
            // Wyczyść wszystkie aktywne stany dotknięcia
            document.querySelectorAll('*').forEach(el => {
                el.style.pointerEvents = '';
            });
            
            // Ustaw właściwe właściwości interakcji
            setTimeout(() => {
                mapContainer.style.touchAction = 'pan-x pan-y';
                document.body.style.touchAction = 'auto';
                
                // Ustaw prawidłowe zdarzenia dla elementów interaktywnych
                const allClickableElements = document.querySelectorAll('.circle-plus, .filter-button, #nearestPinInfo, .location-tracking-toggle, .popup-button, button, input[type="checkbox"], #commentModal, #filterModal, #myModal');
                allClickableElements.forEach(el => {
                    el.style.pointerEvents = 'auto';
                    el.style.zIndex = '1000';
                });
                
                // Kontrole mapy muszą być aktywne
                document.querySelectorAll('.leaflet-control').forEach(el => {
                    el.style.pointerEvents = 'auto';
                    el.style.zIndex = '1000';
                });
                
                // Zapewnij, że elementy Leaflet są interaktywne
                leafletObjects.forEach(el => {
                    el.style.pointerEvents = 'auto';
                });
            }, 100);
        }
    }
    
    // Wywołaj po każdym odświeżeniu mapy
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const result = originalFetch.apply(this, args);
        if (args[0].includes('/render_map')) {
            result.then(() => {
                setTimeout(resetMapInteractions, 300);
            });
        }
        return result;
    };
    
    // Dodaj mechanizm naprawczy, który użytkownik może aktywować w przypadku zablokowania
    document.addEventListener('touchstart', function(e) {
        // Jeśli dotknięcie trwa długo (przytrzymanie) spróbuj naprawić interakcje
        let touchTimeout = setTimeout(() => {
            resetMapInteractions();
        }, 1000);
        
        document.addEventListener('touchend', function clearTouchTimeout() {
            clearTimeout(touchTimeout);
            document.removeEventListener('touchend', clearTouchTimeout);
        }, { once: true });
    });
    
    // Dodaj regularne resetowanie podczas śledzenia
    if (window.intelligentTrackingResetInterval) {
        clearInterval(window.intelligentTrackingResetInterval);
    }
    window.intelligentTrackingResetInterval = setInterval(() => {
        const trackingEnabled = document.getElementById('locationTrackingToggle')?.checked;
        if (trackingEnabled) {
            resetMapInteractions();
        }
    }, 10000);  // Reset co 10 sekund podczas aktywnego śledzenia
});

function clearNavigation() {
    console.log('clearNavigation called');
    
    // Usuń cel nawigacji z localStorage
    localStorage.removeItem('targetLat');
    localStorage.removeItem('targetLon');
    console.log('Removed target from localStorage');
    
    // Resetuj flagę wymuszającą aktualizację
    forceNextUpdate = false;
    
    // Ukryj box z informacjami o nawigacji i przycisk anulowania
    const nearestPinInfo = document.getElementById('nearestPinInfo');
    const cancelBtn = document.getElementById('cancelNavigationBtn');
    nearestPinInfo.classList.remove('show');
    cancelBtn.style.display = 'none';
    console.log('Hidden info box and cancel button');
    
    // Wywołaj endpoint serwera do usunięcia celu nawigacji z sesji
    fetch('/clear_navigation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Najpierw odśwież mapę bez trasy
        return fetch('/render_map');
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('map').innerHTML = html;
        
        // Sprawdź czy jest włączone śledzenie
        const trackingEnabled = document.getElementById('locationTrackingToggle')?.checked;
        
        // Po odświeżeniu mapy, zawsze pokaż informacje o najbliższej toalecie
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    // Wywołaj endpoint do znalezienia najbliższej toalety
                    fetch('/nearest_toilet_distance')
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            const nearestPinText = document.getElementById('nearestPinText');
                            // ZAWSZE ukryj przycisk anulowania dla najbliższej toalety
                            cancelBtn.style.display = 'none';
                            console.log('clearNavigation: Set cancel button to none for nearest toilet');
                            nearestPinText.innerText = `Od twojej lokalizacji do najbliższej toalety jest ${data.distance} - ${data.name}.\nSzacowany czas dotarcia: ${data.duration} min 🚶`;
                            nearestPinInfo.classList.add('show');
                            console.log('clearNavigation: Showed nearest toilet info box');
                            
                            // Dopiero TERAZ restart śledzenia, z opóźnieniem, żeby nie konkurowało z boxem
                            if (trackingEnabled) {
                                console.log('clearNavigation: Will restart tracking in 1s');
                                setTimeout(() => {
                                    stopIntelligentTracking();
                                    startIntelligentTracking();
                                }, 1000); // 1s opóźnienie
                            }
                        }
                    })
                    .catch(error => console.error('Error:', error));
                },
                (error) => {
                    console.error('Error getting location:', error);
                    // Restart śledzenia nawet w przypadku błędu geolokalizacji
                    if (trackingEnabled) {
                        setTimeout(() => {
                            stopIntelligentTracking();
                            startIntelligentTracking();
                        }, 1000);
                    }
                }
            );
        } else {
            // Restart śledzenia nawet jeśli geolokalizacja nie jest dostępna
            if (trackingEnabled) {
                setTimeout(() => {
                    stopIntelligentTracking();
                    startIntelligentTracking();
                }, 1000);
            }
        }
    })
    .catch(error => console.error('Error:', error));
}
