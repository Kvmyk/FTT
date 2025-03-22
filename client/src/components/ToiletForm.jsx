import React, { useState } from 'react';
import axios from 'axios';
import './ToiletForm.css';

function ToiletForm({ onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    userInput: '',
    description: '',
    payable: false,
    onlyForClients: false,
    forDisabled: false,
    rating: '',
    useUserLocation: false,
    weekdayOpenTime: '',
    weekdayCloseTime: '',
    weekendOpenTime: '',
    weekendCloseTime: ''
  });
  
  const [photos, setPhotos] = useState([]);
  const [previews, setPreviews] = useState([]);
  
  // Handle form input changes
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value
    });
  };
  
  // Handle photo upload and preview
  const handlePhotoChange = (e) => {
    const files = Array.from(e.target.files);
    const maxSize = 5 * 1024 * 1024; // 5MB
    const allowedTypes = ['image/jpeg', 'image/png', 'image/jpg'];
    
    // Validate files
    const validFiles = files.filter(file => {
      if (!allowedTypes.includes(file.type)) {
        alert(`File "${file.name}" has invalid format. Allowed formats: PNG, JPG`);
        return false;
      }
      
      if (file.size > maxSize) {
        alert(`File "${file.name}" is too large. Maximum size is 5MB`);
        return false;
      }
      
      return true;
    });
    
    setPhotos(validFiles);
    
    // Create previews
    const newPreviews = validFiles.map(file => URL.createObjectURL(file));
    setPreviews(newPreviews);
  };
  
  // Check for profanity in text
  const checkProfanity = async (text) => {
    try {
      const response = await axios.post('/check_profanity', { text });
      return response.data;
    } catch (error) {
      console.error('Error checking profanity:', error);
      return { status: 'neutral' }; // Default to neutral on error
    }
  };
  
  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.userInput || !formData.description || !formData.rating) {
      alert('Wszystkie pola (nazwa, opis i ocena) muszą być wypełnione.');
      return;
    }
    
    // Validate character limits
    if (formData.userInput.length > 512) {
      alert('Nazwa toalety nie może przekraczać 512 znaków.');
      return;
    }
    
    if (formData.description.length > 512) {
      alert('Opis toalety nie może przekraczać 512 znaków.');
      return;
    }
    
    // Validate rating
    const rating = parseInt(formData.rating, 10);
    if (isNaN(rating) || rating < 1 || rating > 10) {
      alert('Ocena musi być w zakresie od 1 do 10.');
      return;
    }
    
    // Check for profanity
    const profanityCheck = await checkProfanity(formData.description);
    if (profanityCheck.status === 'hate') {
      alert('Opis zawiera mowę nienawiści i nie może zostać dodany.');
      return;
    }
    
    // Create form data for submission
    const submitData = new FormData();
    Object.keys(formData).forEach(key => {
      submitData.append(key, formData[key]);
    });
    
    // Add photos
    if (photos.length > 0) {
      submitData.append('photos', photos[0]);
    }
    
    // Submit the form
    try {
      const response = await axios.post('/submit', submitData);
      if (response.data.status === 'success') {
        onSubmit();
      } else {
        alert('Wystąpił błąd podczas dodawania toalety.');
      }
    } catch (error) {
      console.error('Error submitting toilet form:', error);
      alert('Wystąpił błąd podczas dodawania toalety.');
    }
  };
  
  return (
    <div className="modal">
      <div className="modal-content">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Dodaj toaletę</h2>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            name="userInput"
            placeholder="Wpisz adres..."
            value={formData.userInput}
            onChange={handleChange}
            required
          />
          
          <textarea
            name="description"
            placeholder="Dodaj opis..."
            value={formData.description}
            onChange={handleChange}
            required
          />
          
          <div className="checkbox-group">
            <label>
              <input
                type="checkbox"
                name="payable"
                checked={formData.payable}
                onChange={handleChange}
              />
              Płatna
            </label>
          </div>
          
          <div className="checkbox-group">
            <label>
              <input
                type="checkbox"
                name="onlyForClients"
                checked={formData.onlyForClients}
                onChange={handleChange}
              />
              Tylko dla klientów
            </label>
          </div>
          
          <div className="checkbox-group">
            <label>
              <input
                type="checkbox"
                name="forDisabled"
                checked={formData.forDisabled}
                onChange={handleChange}
              />
              Dla niepełnosprawnych
            </label>
          </div>
          
          <input
            type="number"
            name="rating"
            placeholder="Ocena (1-10)"
            min="1"
            max="10"
            value={formData.rating}
            onChange={handleChange}
            required
          />
          
          <div className="hours-section">
            <h4>Godziny otwarcia (dni powszednie)</h4>
            <div className="hours-inputs">
              <label>
                Od:
                <input
                  type="time"
                  name="weekdayOpenTime"
                  value={formData.weekdayOpenTime}
                  onChange={handleChange}
                />
              </label>
              <label>
                Do:
                <input
                  type="time"
                  name="weekdayCloseTime"
                  value={formData.weekdayCloseTime}
                  onChange={handleChange}
                />
              </label>
            </div>
          </div>
          
          <div className="hours-section">
            <h4>Godziny otwarcia (weekendy)</h4>
            <div className="hours-inputs">
              <label>
                Od:
                <input
                  type="time"
                  name="weekendOpenTime"
                  value={formData.weekendOpenTime}
                  onChange={handleChange}
                />
              </label>
              <label>
                Do:
                <input
                  type="time"
                  name="weekendCloseTime"
                  value={formData.weekendCloseTime}
                  onChange={handleChange}
                />
              </label>
            </div>
          </div>
          
          <div className="photo-upload">
            <label>Dodaj zdjęcie:</label>
            <input
              type="file"
              accept=".jpg,.png"
              onChange={handlePhotoChange}
              multiple
            />
            
            {previews.length > 0 && (
              <div className="image-previews">
                {previews.map((preview, index) => (
                  <img
                    key={index}
                    src={preview}
                    alt={`Preview ${index}`}
                    className="image-preview"
                  />
                ))}
              </div>
            )}
          </div>
          
          <div className="location-checkbox">
            <label className="switch">
              <input
                type="checkbox"
                name="useUserLocation"
                checked={formData.useUserLocation}
                onChange={handleChange}
              />
              <span className="slider"></span>
            </label>
            <span className="switch-label">Użyj mojej lokalizacji</span>
          </div>
          
          <button type="submit" className="submit-button">Gotowe</button>
        </form>
      </div>
    </div>
  );
}

export default ToiletForm;