import React, { useEffect, useState, useRef, useContext } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import axios from 'axios';
import { AppContext } from '../context/AppContext';
import 'leaflet/dist/leaflet.css';
import './Map.css';

// Custom icons
const userIcon = new L.Icon({
  iconUrl: '/static/user_icon.png',
  iconSize: [50, 50],
  iconAnchor: [25, 50],
  popupAnchor: [0, -50],
  shadowSize: [50, 50]
});

const toiletIcon = new L.Icon({
  iconUrl: '/static/toilet_icon.png',
  iconSize: [50, 50],
  iconAnchor: [25, 50],
  popupAnchor: [0, -50],
  shadowSize: [50, 50]
});

// Component to update map center when user location changes
function MapUpdater({ center }) {
  const map = useMap();
  
  useEffect(() => {
    if (center.lat && center.lng) {
      map.setView([center.lat, center.lng], map.getZoom());
    }
  }, [center, map]);
  
  return null;
}

function Map({ trackingEnabled, onOpenCommentForm }) {
  const { state, dispatch } = useContext(AppContext);
  const [mapData, setMapData] = useState({
    markers: [],
    userMarker: null,
    center: { lat: 50.6751, lng: 17.9213 },
    route: null,
    selectedTarget: null
  });
  const watchId = useRef(null);
  const lastPosition = useRef(null);
  
  const MIN_DISTANCE = 25; // Minimum distance in meters to trigger update
  
  // Function to calculate distance between two coordinates
  const calculateDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371e3; // Earth's radius in meters
    const φ1 = lat1 * Math.PI/180;
    const φ2 = lat2 * Math.PI/180;
    const Δφ = (lat2-lat1) * Math.PI/180;
    const Δλ = (lon2-lon1) * Math.PI/180;

    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c; // in meters
  };
  
  // Check if coordinates are in Opole province
  const isInOpoleProvince = (lat, lon) => {
    const opoleBounds = {
      north: 51.0,
      south: 49.5,
      west: 16.5,
      east: 18.5
    };
    
    return lat >= opoleBounds.south && lat <= opoleBounds.north &&
           lon >= opoleBounds.west && lon <= opoleBounds.east;
  };
  
  // Start location tracking
  const startTracking = () => {
    if (!navigator.geolocation) {
      console.error('Geolocation is not supported by this browser.');
      return;
    }
    
    stopTracking();
    
    watchId.current = navigator.geolocation.watchPosition(
      (position) => {
        const currentPosition = {
          lat: position.coords.latitude,
          lon: position.coords.longitude
        };
        
        // Check if in Opole province
        if (!isInOpoleProvince(currentPosition.lat, currentPosition.lon)) {
          alert('Znajdujesz się poza województwem opolskim. Nawigacja jest dostępna tylko w województwie opolskim.');
          stopTracking();
          return;
        }
        
        // Check if position has changed significantly
        if (!lastPosition.current || calculateDistance(
          lastPosition.current.lat, lastPosition.current.lon,
          currentPosition.lat, currentPosition.lon
        ) > MIN_DISTANCE) {
          lastPosition.current = currentPosition;
          
          // Update user location in backend
          axios.post('/update_user_location', {
            user_lat: currentPosition.lat,
            user_lon: currentPosition.lon
          })
          .then(response => {
            if (response.data.status === 'success') {
              fetchMapData();
            }
          })
          .catch(error => console.error('Error updating location:', error));
        }
      },
      (error) => {
        console.error('Error getting location:', error);
        alert(`Error getting location: ${error.message}`);
        stopTracking();
      },
      {
        enableHighAccuracy: true,
        maximumAge: 30000,
        timeout: 27000
      }
    );
  };
  
  // Stop location tracking
  const stopTracking = () => {
    if (watchId.current) {
      navigator.geolocation.clearWatch(watchId.current);
      watchId.current = null;
    }
  };
  
  // Fetch map data from API
  const fetchMapData = () => {
    axios.get('/api/map-data')
      .then(response => {
        const data = response.data;
        setMapData({
          markers: data.markers || [],
          userMarker: data.userMarker,
          center: {
            lat: data.center.lat,
            lng: data.center.lon
          },
          route: data.route,
          selectedTarget: data.selectedTarget
        });
      })
      .catch(error => console.error('Error fetching map data:', error));
  };
  
  // Navigate to a toilet
  const navigateToToilet = (targetLat, targetLon) => {
    if (!mapData.userMarker) {
      alert('Twoja lokalizacja nie jest ustawiona. Włącz śledzenie lokalizacji.');
      return;
    }
    
    if (!isInOpoleProvince(targetLat, targetLon)) {
      alert('Marker znajduje się poza województwem opolskim. Nawigacja jest dostępna tylko do markerów w województwie opolskim.');
      return;
    }
    
    axios.post('/navigate', {
      user_lat: mapData.userMarker.lat,
      user_lon: mapData.userMarker.lon,
      target_lat: targetLat,
      target_lon: targetLon
    })
    .then(response => {
      if (response.data.status === 'success') {
        localStorage.setItem('targetLat', targetLat);
        localStorage.setItem('targetLon', targetLon);
        fetchMapData();
      }
    })
    .catch(error => console.error('Error navigating to toilet:', error));
  };
  
  // Initialize tracking based on trackingEnabled prop
  useEffect(() => {
    if (trackingEnabled) {
      startTracking();
    } else {
      stopTracking();
    }
    
    return () => stopTracking();
  }, [trackingEnabled]);
  
  // Initial fetch of map data
  useEffect(() => {
    fetchMapData();
    
    // Set up a refresh interval
    const intervalId = setInterval(fetchMapData, 30000);
    
    return () => clearInterval(intervalId);
  }, []);
  
  // Render toilet popup content
  const renderToiletPopup = (marker) => {
    const isWithinRange = mapData.userMarker ? 
      (calculateDistance(
        mapData.userMarker.lat, mapData.userMarker.lon, 
        marker.lat, marker.lon
      ) / 1000) <= 10 : false;
    
    return (
      <div className="toilet-popup">
        <h2>{marker.name}</h2>
        <p>{marker.description}</p>
        <p><strong>Płatna:</strong> {marker.payable ? 'TAK' : 'NIE'}</p>
        <p><strong>Tylko dla klientów:</strong> {marker.onlyForClients ? 'TAK' : 'NIE'}</p>
        <p><strong>Dla niepełnosprawnych:</strong> {marker.forDisabled ? 'TAK' : 'NIE'}</p>
        <p><strong>Ocena:</strong> {marker.rating}</p>
        
        {/* Opening hours info */}
        {(marker.weekday_open && marker.weekday_close) || (marker.weekend_open && marker.weekend_close) ? (
          <>
            <p><strong>Godziny otwarcia:</strong></p>
            <p>Dni powszednie: {marker.weekday_open && marker.weekday_close ? 
              `${marker.weekday_open} - ${marker.weekday_close}` : 'Nieznane'}</p>
            <p>Weekendy: {marker.weekend_open && marker.weekend_close ? 
              `${marker.weekend_open} - ${marker.weekend_close}` : 'Nieznane'}</p>
          </>
        ) : null}
        
        {/* Photo if available */}
        {marker.photo && (
          <div className="toilet-photo">
            <img 
              src={`/static/${marker.photo}`} 
              alt={marker.name}
              style={{
                maxWidth: '150px', 
                maxHeight: '150px',
                borderRadius: '4px'
              }}
            />
          </div>
        )}
        
        {/* Comments section */}
        {marker.comments && marker.comments.length > 0 && (
          <div className="comments-section">
            <h3>Komentarze</h3>
            <div className="comment">
              <p><strong>Ocena:</strong> {marker.comments[0].rating}</p>
              <p>{marker.comments[0].comment}</p>
            </div>
            {marker.comments.length > 1 && (
              <button className="more-comments">
                Więcej komentarzy ({marker.comments.length - 1})
              </button>
            )}
          </div>
        )}
        
        {/* Navigation button */}
        <button 
          className="popup-button navigate-button"
          onClick={() => navigateToToilet(marker.lat, marker.lon)}
          disabled={!isWithinRange}
          style={{
            opacity: isWithinRange ? 1 : 0.7,
            pointerEvents: isWithinRange ? 'auto' : 'none'
          }}
        >
          Nawiguj
        </button>
        
        {/* Comment button */}
        <button 
          className="popup-button comment-button"
          onClick={() => onOpenCommentForm(marker.lat, marker.lon)}
        >
          Dodaj komentarz
        </button>
      </div>
    );
  };
  
  return (
    <div className="map-container">
      <MapContainer
        center={[mapData.center.lat, mapData.center.lng]} 
        zoom={15}
        style={{ height: '100vh', width: '100%' }}
        attributionControl={true}
        zoomControl={true}
        doubleClickZoom={true}
        scrollWheelZoom={true}
        dragging={true}
        animate={true}
        easeLinearity={0.35}
      >
        {/* Important: Use Cartodb positron tile layer as requested */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          subdomains="abcd"
          maxZoom={19}
        />
        
        {/* Update map center when user location changes */}
        <MapUpdater center={mapData.center} />
        
        {/* User marker */}
        {mapData.userMarker && (
          <Marker 
            position={[mapData.userMarker.lat, mapData.userMarker.lon]} 
            icon={userIcon}
          >
            <Popup>
              <div>
                <h2>User Location</h2>
                <p>{mapData.userMarker.description}</p>
              </div>
            </Popup>
          </Marker>
        )}
        
        {/* Toilet markers */}
        {mapData.markers.map((marker, index) => (
          marker.name !== "User Location" && (
            <Marker 
              key={`toilet-${marker.lat}-${marker.lon}-${index}`}
              position={[marker.lat, marker.lon]} 
              icon={toiletIcon}
            >
              <Popup minWidth={250} maxHeight={300}>
                {renderToiletPopup(marker)}
              </Popup>
            </Marker>
          )
        ))}
        
        {/* Route polyline */}
        {mapData.route && (
          <>
            <Polyline 
              positions={mapData.route.coordinates}
              color="#d00000"
              weight={5}
              opacity={0.7}
            />
            {mapData.route.coordinates.length > 0 && (
              <Marker
                position={mapData.route.coordinates[Math.floor(mapData.route.coordinates.length / 2)]}
                icon={L.divIcon({
                  className: 'route-distance-label',
                  html: `<div class="distance-label">${mapData.route.distance_text}</div>`,
                  iconSize: [100, 20],
                  iconAnchor: [50, 10]
                })}
              />
            )}
          </>
        )}
      </MapContainer>
    </div>
  );
}

export default Map;