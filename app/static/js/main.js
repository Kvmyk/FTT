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
        if (!sessionStorage.getItem('reloaded')) {
            sessionStorage.setItem('reloaded', 'true');
            window.location.reload();
        }
        document.getElementById('loadingOverlay').style.display = 'none';
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
    var lat = document.getElementById('commentModal').dataset.lat;
    var lon = document.getElementById('commentModal').dataset.lon;
    var comment = document.getElementById('commentText').value;
    var rating = document.getElementById('commentRating').value;

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
