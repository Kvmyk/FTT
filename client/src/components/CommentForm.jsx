import React, { useState } from 'react';
import axios from 'axios';
import './CommentForm.css';

function CommentForm({ location, onClose, onSubmit }) {
  const [comment, setComment] = useState('');
  const [rating, setRating] = useState('');
  
  // Validate rating
  const validateRating = () => {
    const ratingNum = parseInt(rating, 10);
    if (isNaN(ratingNum) || ratingNum < 1 || ratingNum > 10) {
      alert('Ocena musi być w zakresie od 1 do 10.');
      return false;
    }
    return true;
  };
  
  // Check for profanity
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
    
    // Validate fields
    if (!comment || !rating) {
      alert('Wszystkie pola muszą być wypełnione.');
      return;
    }
    
    // Check comment length
    if (comment.length > 512) {
      alert('Komentarz nie może przekraczać 512 znaków.');
      return;
    }
    
    // Validate rating
    if (!validateRating()) {
      return;
    }
    
    // Check for profanity
    const profanityCheck = await checkProfanity(comment);
    if (profanityCheck.status === 'hate') {
      alert('Komentarz zawiera mowę nienawiści i nie może zostać dodany.');
      return;
    }
    
    // Create form data
    const formData = new FormData();
    formData.append('lat', location.lat);
    formData.append('lon', location.lon);
    formData.append('comment', comment);
    formData.append('rating', rating);
    
    // Submit the form
    try {
      const response = await axios.post('/add_comment', formData);
      if (response.data.status === 'success') {
        onSubmit();
      } else {
        alert('Wystąpił błąd podczas dodawania komentarza.');
      }
    } catch (error) {
      console.error('Error submitting comment:', error);
      alert('Wystąpił błąd podczas dodawania komentarza.');
    }
  };
  
  return (
    <div className="modal" id="commentModal">
      <div className="modal-content">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Dodaj komentarz</h2>
        <form onSubmit={handleSubmit}>
          <textarea
            id="commentText"
            placeholder="Twój komentarz..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            required
          />
          
          <input
            type="number"
            id="commentRating"
            placeholder="Ocena (1-10)"
            min="1"
            max="10"
            value={rating}
            onChange={(e) => setRating(e.target.value)}
            required
          />
          
          <button type="submit" className="submit-button">Dodaj komentarz</button>
        </form>
      </div>
    </div>
  );
}

export default CommentForm;