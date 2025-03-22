import React, { useState, useEffect } from 'react';
import { AppProvider } from './context/AppContext';
import Map from './components/Map';
import ToiletForm from './components/ToiletForm';
import CommentForm from './components/CommentForm';
import FilterModal from './components/FilterModal';
import './App.css';

function App() {
  const [showToiletForm, setShowToiletForm] = useState(false);
  const [showCommentForm, setShowCommentForm] = useState(false);
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState(null);
  
  // Track if location tracking is enabled
  const [trackingEnabled, setTrackingEnabled] = useState(
    localStorage.getItem('trackingEnabled') === 'true'
  );

  useEffect(() => {
    localStorage.setItem('trackingEnabled', trackingEnabled);
  }, [trackingEnabled]);

  return (
    <AppProvider>
      <div className="app">
        <Map 
          trackingEnabled={trackingEnabled}
          onOpenCommentForm={(lat, lon) => {
            setSelectedLocation({ lat, lon });
            setShowCommentForm(true);
          }}
        />
        
        {/* Add Toilet button */}
        <button 
          className="circle-plus" 
          onClick={() => setShowToiletForm(true)}
          aria-label="Add toilet"
        >
          +
        </button>
        
        {/* Filters button */}
        <button 
          className="filter-button" 
          onClick={() => setShowFilterModal(true)}
          aria-label="Filter"
        >
          <i className="filter-icon">⚙️</i>
        </button>
        
        {/* Location tracking toggle */}
        <div className="location-tracking-toggle">
          <label className="switch">
            <input 
              type="checkbox" 
              checked={trackingEnabled}
              onChange={() => setTrackingEnabled(!trackingEnabled)}
            />
            <span className="slider"></span>
          </label>
          <span className="switch-label">Śledzenie lokalizacji</span>
        </div>
        
        {/* Modals */}
        {showToiletForm && (
          <ToiletForm 
            onClose={() => setShowToiletForm(false)} 
            onSubmit={() => {
              setShowToiletForm(false);
              // Refresh map data
            }}
          />
        )}
        
        {showCommentForm && selectedLocation && (
          <CommentForm 
            location={selectedLocation}
            onClose={() => setShowCommentForm(false)} 
            onSubmit={() => {
              setShowCommentForm(false);
              // Refresh map data
            }}
          />
        )}
        
        {showFilterModal && (
          <FilterModal 
            onClose={() => setShowFilterModal(false)} 
            onApply={() => {
              setShowFilterModal(false);
              // Refresh map data
            }}
          />
        )}
        
        {/* Copyright Footer */}
        <footer className="copyright-footer">
          <p>© 2025 Find My Throne - All Rights Reserved</p>
        </footer>
      </div>
    </AppProvider>
  );
}

export default App;