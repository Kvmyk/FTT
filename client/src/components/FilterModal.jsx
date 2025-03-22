import React, { useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { AppContext } from '../context/AppContext';
import './FilterModal.css';

function FilterModal({ onClose, onApply }) {
  const { state, dispatch } = useContext(AppContext);
  const [filters, setFilters] = useState({
    filterPayable: false,
    filterForClients: false,
    filterForDisabled: false,
    filterRating: '0'
  });
  
  // Load filters from context on component mount
  useEffect(() => {
    if (state.filters) {
      setFilters(state.filters);
    }
  }, [state.filters]);
  
  // Handle filter changes
  const handleFilterChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFilters({
      ...filters,
      [name]: type === 'checkbox' ? checked : value
    });
  };
  
  // Apply filters
  const applyFilters = async () => {
    // Validate rating
    const rating = parseInt(filters.filterRating, 10);
    if (isNaN(rating) || rating < 0 || rating > 10) {
      alert('Ocena musi być w zakresie od 0 do 10.');
      return;
    }
    
    try {
      const response = await axios.post('/apply_filters', filters);
      if (response.data.status === 'success') {
        // Update filters in context
        dispatch({ type: 'SET_FILTERS', payload: filters });
        
        // Close modal and call parent's onApply
        onApply();
      } else {
        alert('Wystąpił błąd podczas stosowania filtrów.');
      }
    } catch (error) {
      console.error('Error applying filters:', error);
      alert('Wystąpił błąd podczas stosowania filtrów.');
    }
  };
  
  // Show all toilets (clear filters)
  const showAllToilets = async () => {
    const clearedFilters = {
      filterPayable: false,
      filterForClients: false,
      filterForDisabled: false,
      filterRating: '0'
    };
    
    try {
      const response = await axios.post('/apply_filters', clearedFilters);
      if (response.data.status === 'success') {
        // Update filters in context
        dispatch({ type: 'SET_FILTERS', payload: clearedFilters });
        
        // Update local state
        setFilters(clearedFilters);
        
        // Close modal and call parent's onApply
        onApply();
      } else {
        alert('Wystąpił błąd podczas czyszczenia filtrów.');
      }
    } catch (error) {
      console.error('Error clearing filters:', error);
      alert('Wystąpił błąd podczas czyszczenia filtrów.');
    }
  };
  
  return (
    <div className="modal" id="filterModal">
      <div className="modal-content">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Filtruj toalety</h2>
        
        <div className="filter-options">
          <div className="filter-checkbox">
            <label>
              <input
                type="checkbox"
                name="filterPayable"
                checked={filters.filterPayable}
                onChange={handleFilterChange}
              />
              Tylko płatne
            </label>
          </div>
          
          <div className="filter-checkbox">
            <label>
              <input
                type="checkbox"
                name="filterForClients"
                checked={filters.filterForClients}
                onChange={handleFilterChange}
              />
              Tylko dla klientów
            </label>
          </div>
          
          <div className="filter-checkbox">
            <label>
              <input
                type="checkbox"
                name="filterForDisabled"
                checked={filters.filterForDisabled}
                onChange={handleFilterChange}
              />
              Dla niepełnosprawnych
            </label>
          </div>
          
          <div className="filter-rating">
            <label>
              Minimalna ocena:
              <input
                type="number"
                name="filterRating"
                min="0"
                max="10"
                value={filters.filterRating}
                onChange={handleFilterChange}
              />
            </label>
          </div>
        </div>
        
        <div className="filter-buttons">
          <button onClick={applyFilters} className="apply-button">
            Zastosuj filtry
          </button>
          <button onClick={showAllToilets} className="show-all-button">
            Pokaż wszystkie toalety
          </button>
        </div>
      </div>
    </div>
  );
}

export default FilterModal;