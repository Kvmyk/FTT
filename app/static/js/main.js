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
            nearestPinText.innerText = `Od twojej lokalizacji do najbliższej toalety jest ${data.distance} - ${data.name}. Szacowany czas dotarcia: ${data.duration} minut pieszo.`;
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
    const useUserLocation = document.getElementById('useUserLocation').checked;
    const userInput = document.getElementById('userInput').value;
    const description = document.getElementById('descriptionInput').value;
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

function navigateToToilet(targetLat, targetLon) {
    localStorage.setItem('targetLat', targetLat);
    localStorage.setItem('targetLon', targetLon);

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLat = position.coords.latitude;
                const userLon = position.coords.longitude;
                
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
                        return fetch('/render_map');
                    }
                })
                .then(response => response.text())
                .then(html => {
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
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const nearestPinInfo = document.getElementById('nearestPinInfo');
                        const nearestPinText = document.getElementById('nearestPinText');
                        nearestPinText.innerText = `Od twojej lokalizacji do toalety jest ${data.distance} – ${data.name}. Szacowany czas dotarcia: ${data.duration} minut pieszo.`;
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
    container.innerHTML = ''; // Wyczyść poprzednie podglądy

    const files = Array.from(this.files);
    const resizedFiles = [];

    files.forEach(file => {
        if (file.type.startsWith('image/')) {
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
        }
    });

    this.files = new FileList(...resizedFiles);
});
