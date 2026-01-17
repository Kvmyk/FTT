# Reserver (Find My Throne) - Agent Guidelines

This document provides essential information for agentic coding assistants working on the **Find My Throne** project - a Flask web application for locating public toilets.

## Project Overview

**Find My Throne** is a Python Flask web application that helps users find the nearest public toilets with real-time navigation, user reviews, and content moderation via Google Gemini API.

- **Live Site**: https://findmythrone.net/
- **Language**: Python 3.8+
- **Framework**: Flask 2.x
- **Database**: SQLite 3.x
- **Key Features**: Geolocation, routing (OSRM), hate speech detection (Gemini), admin panel

## Running the Application

### Development Server
```bash
python run.py
# Or
python -m flask run --host=0.0.0.0 --port=5000 --debug
```

### With Virtual Environment
```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r app/requirements.txt

# Run server
python run.py
```

## Testing

### Running Tests
```bash
# Run all tests with pytest
pytest

# Run tests in specific directory
pytest app/

# Run a single test file
pytest app/test_filename.py

# Run a specific test function
pytest app/test_filename.py::test_function_name

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app
```

**Note**: Currently no test files exist. Tests should be created in `app/tests/` directory following pytest conventions.

## Code Style Guidelines

### Imports
- Group imports in this order:
  1. Standard library imports
  2. Third-party imports (Flask, SQLite, etc.)
  3. Local application imports (app.*)
- Each group separated by a blank line
- Sort alphabetically within groups

**Example**:
```python
import os
import logging
from contextlib import closing

from flask import Blueprint, jsonify, request
from geopy.geocoders import Nominatim

from app.models.database import db
from app.utils import find_nearest_marker
```

### Naming Conventions
- **Functions and variables**: `snake_case` (e.g., `get_coordinates`, `user_location`)
- **Classes**: `PascalCase` (e.g., `DatabaseManager`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ADMIN_USER`)
- **Private methods**: Prefix with single underscore (e.g., `_internal_helper`)
- **Blueprint instances**: `name_bp` (e.g., `api_bp`, `admin_bp`, `views_bp`)

### Formatting
- **Indentation**: 4 spaces (no tabs)
- **Line length**: Aim for 100-120 characters max
- **Blank lines**: 2 blank lines between top-level functions/classes
- **Strings**: Single quotes preferred, but double quotes acceptable for consistency

### Type Hints
- Use type hints for function signatures where it improves clarity
- Not strictly enforced but encouraged for new code
- Example:
```python
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates."""
    ...
```

### Docstrings
- Use triple-quoted strings for all public functions, classes, and modules
- Keep docstrings concise but informative
- Format:
```python
def function_name(param1, param2):
    """Brief description of what the function does.
    
    Optional longer description if needed.
    """
```

### Error Handling
- Use try-except blocks for external operations (DB, API calls, file I/O)
- Always log errors with `logging.error()` or `logging.warning()`
- Return meaningful error responses with appropriate HTTP status codes
- For database operations, use `contextlib.closing()` context manager
- Fail gracefully: Don't block users if optional features fail (e.g., hate speech check)

**Example**:
```python
try:
    with closing(self.get_connection()) as conn:
        with closing(conn.cursor()) as cursor:
            # Database operations
            ...
except sqlite3.Error as e:
    logging.error(f"Database error: {e}")
    return None
```

### Database Patterns
- Use `sqlite3.Row` for row factory to access columns by name
- Always use context managers (`with closing()`) for connections and cursors
- Use parameterized queries to prevent SQL injection: `cursor.execute(query, (param1, param2))`
- Boolean database fields stored as INTEGER (0/1), convert to bool in Python

### API Design
- Use Flask Blueprints for route organization
- RESTful endpoints when possible
- JSON request/response format
- Return status with message:
```python
return jsonify({'status': 'success', 'data': result})
return jsonify({'status': 'error', 'message': 'Description'}), 400
```

### Environment Variables
- Use `python-dotenv` for environment variable management
- Load with `load_dotenv()` at module top
- Access with `os.environ.get('VAR_NAME', 'default_value')`
- Never commit `.env` files - keep them in `.gitignore`
- Required variables: `KEY`, `GEMINI_API_KEY`, `USER_AGENT`, `ADMIN_USER`, `ADMIN_PASSWORD`

### Logging
- Use Python's `logging` module
- Configure at application entry point: `logging.basicConfig(level=logging.DEBUG)`
- Log levels:
  - `DEBUG`: Detailed information for debugging
  - `INFO`: General informational messages (e.g., "Route fetched successfully")
  - `WARNING`: Warning messages (e.g., missing optional config)
  - `ERROR`: Error messages for failures

### Session Management
- Use Flask-Session with filesystem storage
- Session timeout: 3600 seconds (1 hour)
- Store admin authentication in session: `session['admin_logged_in']`
- Use `@login_required` decorator for protected admin routes

## Project Structure
```
Reserver/
├── run.py                 # Application entry point
├── app/
│   ├── __init__.py       # Flask app factory (create_app)
│   ├── requirements.txt  # Python dependencies
│   ├── .env             # Environment variables (gitignored)
│   ├── models/
│   │   └── database.py  # DatabaseManager class, SQLite operations
│   ├── routes/
│   │   ├── api.py       # API endpoints (/api/*)
│   │   ├── views.py     # Page rendering routes
│   │   └── admin.py     # Admin panel (/admin/*)
│   ├── static/          # Static files (images, CSS, JS)
│   ├── templates/       # Jinja2 HTML templates
│   ├── data/            # SQLite database storage
│   └── utils.py         # Helper functions (haversine, routing, etc.)
├── flask_session/       # Session storage (auto-generated)
└── legacy/              # Old code (do not modify)
```

## Common Tasks

### Adding a New API Endpoint
1. Add route to appropriate blueprint in `app/routes/`
2. Import required functions from `app.utils` or `app.models.database`
3. Validate input data and handle errors
4. Return JSON response with status

### Database Schema Changes
1. Modify table creation in `DatabaseManager.setup_database()` in `app/models/database.py`
2. Add corresponding methods for CRUD operations
3. Update existing functions to handle new fields
4. Test with a fresh database or migration

### Content Moderation Integration
- Use `is_hate_speech(text)` from `app.utils` for user-generated content
- Requires `GEMINI_API_KEY` in environment
- Returns `True` if offensive content detected, `False` otherwise
- Apply to: user reviews, toilet descriptions, comments

## Important Notes

- **No package.json**: This is a Python project, not Node.js
- **No tests currently**: Create tests in `app/tests/` using pytest
- **Geographic restrictions**: App only works within Opole Province, Poland (see `isInOpoleProvince()` in utils.py)
- **OSRM routing**: Uses public OSRM server at https://router.project-osrm.org
- **Security**: Admin credentials are environment-based; never hardcode in production

## References

- Flask Documentation: https://flask.palletsprojects.com/
- SQLite Python: https://docs.python.org/3/library/sqlite3.html
- pytest Documentation: https://docs.pytest.org/
- Google Gemini API: https://ai.google.dev/
