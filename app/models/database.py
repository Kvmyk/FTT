import sqlite3
import os
from contextlib import closing
import logging

class DatabaseManager:
    def __init__(self, db_path='app/data/toilets.db'):
        # Ensure we use an absolute path relative to the project root
        # __file__ is inside app/models/
        # We want to reach app/data/toilets.db
        # Option 1: base_dir is root of repo. Then db_path='app/data/toilets.db'
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, db_path)
        
        # Verify if directory exists, if not, check inside 'data' relative to root
        if not os.path.exists(os.path.dirname(self.db_path)):
             # Fallback: create directory if it doesn't exist
             os.makedirs(os.path.dirname(self.db_path))

        logging.info(f"DatabaseManager initialized with path: {self.db_path}")
        self.setup_database()

    def setup_database(self):
        """Initialize SQLite database and create tables if they don't exist."""
        try:
            with closing(self.get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    # Create toilets table
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS toilets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lat REAL NOT NULL,
                        lon REAL NOT NULL,
                        name TEXT,
                        place_name TEXT,
                        description TEXT,
                        payable INTEGER,
                        onlyForClients INTEGER,
                        forDisabled INTEGER,
                        rating REAL,
                        base_rating REAL,
                        weekday_open TEXT,
                        weekday_close TEXT,
                        weekend_open TEXT,
                        weekend_close TEXT,
                        photo TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''')
                    
                    # Create comments table
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS comments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        toilet_id INTEGER,
                        comment TEXT,
                        rating REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (toilet_id) REFERENCES toilets (id)
                    )
                    ''')
                    conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error setting up database: {e}")

    def get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logging.error(f"Database connection failed: {e}")
            raise

    def get_all_toilets(self):
        """Loads all toilets and their comments."""
        markers = []
        try:
            with closing(self.get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute('SELECT * FROM toilets')
                    toilets = cursor.fetchall()
                    
                    for toilet in toilets:
                        marker = dict(toilet)
                        
                        # Type conversion
                        marker['payable'] = bool(marker['payable'])
                        marker['onlyForClients'] = bool(marker['onlyForClients'])
                        marker['forDisabled'] = bool(marker['forDisabled'])
                        
                        # Fetch comments
                        cursor.execute('SELECT comment, rating FROM comments WHERE toilet_id = ?', (toilet['id'],))
                        comments = [dict(c) for c in cursor.fetchall()]
                        if comments:
                            marker['comments'] = comments
                        
                        markers.append(marker)
        except sqlite3.Error as e:
            logging.error(f"Error loading toilets: {e}")
        return markers

    def add_toilet(self, marker_data):
        """Adds a new toilet to the database."""
        try:
            with closing(self.get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute('''
                        INSERT INTO toilets (lat, lon, name, place_name, description, payable, 
                                            onlyForClients, forDisabled, rating, 
                                            base_rating, weekday_open, weekday_close,
                                            weekend_open, weekend_close, photo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        marker_data['lat'],
                        marker_data['lon'],
                        marker_data.get('name', 'Unknown'),
                        marker_data.get('place_name', ''),
                        marker_data.get('description', ''),
                        1 if marker_data.get('payable', False) else 0,
                        1 if marker_data.get('onlyForClients', False) else 0,
                        1 if marker_data.get('forDisabled', False) else 0,
                        float(marker_data.get('rating', 0)),
                        float(marker_data.get('base_rating', 0)),
                        marker_data.get('weekday_open', ''),
                        marker_data.get('weekday_close', ''),
                        marker_data.get('weekend_open', ''),
                        marker_data.get('weekend_close', ''),
                        marker_data.get('photo', None)
                    ))
                    conn.commit()
                    return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error adding toilet: {e}")
            return None

    def add_comment(self, toilet_id, comment, rating):
        """Adds a comment to a toilet."""
        try:
            with closing(self.get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute('''
                        INSERT INTO comments (toilet_id, comment, rating)
                        VALUES (?, ?, ?)
                    ''', (toilet_id, comment, float(rating)))
                    conn.commit()
                    return True
        except sqlite3.Error as e:
            logging.error(f"Error adding comment: {e}")
            return False

    def delete_toilet(self, toilet_id):
        """Deletes a toilet and its comments."""
        try:
            with closing(self.get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute('DELETE FROM comments WHERE toilet_id = ?', (toilet_id,))
                    cursor.execute('DELETE FROM toilets WHERE id = ?', (toilet_id,))
                    conn.commit()
                    return True
        except sqlite3.Error as e:
            logging.error(f"Error deleting toilet: {e}")
            return False

    def update_toilet(self, toilet_id, data):
        """Updates toilet data."""
        try:
            with closing(self.get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute('''
                        UPDATE toilets SET 
                            name = ?, 
                            place_name = ?,
                            description = ?, 
                            payable = ?,
                            onlyForClients = ?,
                            forDisabled = ?,
                            rating = ?,
                            weekday_open = ?,
                            weekday_close = ?,
                            weekend_open = ?,
                            weekend_close = ?
                        WHERE id = ?
                    ''', (
                        data.get('name', ''),
                        data.get('place_name', ''),
                        data.get('description', ''),
                        1 if data.get('payable', False) else 0,
                        1 if data.get('onlyForClients', False) else 0,
                        1 if data.get('forDisabled', False) else 0,
                        float(data.get('rating', 0)),
                        data.get('weekday_open', ''),
                        data.get('weekday_close', ''),
                        data.get('weekend_open', ''),
                        data.get('weekend_close', ''),
                        toilet_id
                    ))
                    conn.commit()
                    return True
        except sqlite3.Error as e:
            logging.error(f"Error updating toilet: {e}")
            return False

# Global database instance
db = DatabaseManager()
