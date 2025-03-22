import React, { createContext, useReducer } from 'react';

// Initial state
const initialState = {
  filters: {
    filterPayable: false,
    filterForClients: false,
    filterForDisabled: false,
    filterRating: '0'
  },
  userLocation: null,
  selectedTarget: null
};

// Create context
export const AppContext = createContext();

// Reducer function
const reducer = (state, action) => {
  switch (action.type) {
    case 'SET_FILTERS':
      return { ...state, filters: action.payload };
    case 'SET_USER_LOCATION':
      return { ...state, userLocation: action.payload };
    case 'SET_TARGET':
      return { ...state, selectedTarget: action.payload };
    default:
      return state;
  }
};

// Provider component
export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
};