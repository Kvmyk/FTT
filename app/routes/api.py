from flask import Blueprint, jsonify, request, session
from app.models.database import db
from app.utils import find_nearest_marker, get_route, isInOpoleProvince, is_hate_speech
import uuid
import logging

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/toilets', methods=['GET'])
def get_toilets():
    """Returns toilets, optionally filtered."""
    payable = request.args.get('payable')
    for_disabled = request.args.get('forDisabled')
    only_clients = request.args.get('onlyForClients')
    min_rating = request.args.get('rating')

    toilets = db.get_all_toilets()
    
    filtered = []
    for t in toilets:
        # Konwersja stringów 'true'/'false' z query params
        if payable == 'true' and not t.get('payable'):
            continue
        if for_disabled == 'true' and not t.get('forDisabled'):
            continue
        if only_clients == 'true' and not t.get('onlyForClients'):
            continue
        if min_rating and float(t.get('rating', 0)) < float(min_rating):
            continue
        filtered.append(t)

    return jsonify(filtered)

@api_bp.route('/route', methods=['POST'])
def calculate_route():
    """
    Calculates route from user location to a destination.
    Expects JSON: { "lat": float, "lon": float, "dest_lat": float, "dest_lon": float }
    """
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_lat = data.get('lat')
    user_lon = data.get('lon')
    
    # Check if user is in supported area (Opole Province)
    if not isInOpoleProvince(user_lat, user_lon):
        return jsonify({'status': 'error', 'message': 'Poza obszarem działania (Woj. Opolskie)'}), 400

    # If destination provided explicitly
    if 'dest_lat' in data and 'dest_lon' in data:
        dest_lat = data['dest_lat']
        dest_lon = data['dest_lon']
    else:
        # Find nearest toilet logic
        # Retrieve filters from request or session if needed
        all_toilets = db.get_all_toilets()
        user_marker = {'lat': user_lat, 'lon': user_lon, 'name': 'User'}
        nearest = find_nearest_marker(user_marker, all_toilets)
        
        if not nearest:
            return jsonify({'status': 'error', 'message': 'Nie znaleziono toalet w pobliżu'}), 404
            
        dest_lat = nearest['lat']
        dest_lon = nearest['lon']

    # Calculate route using OSRM
    route = get_route(user_lat, user_lon, dest_lat, dest_lon)
    
    if route:
        return jsonify({'status': 'success', 'route': route, 'destination': {'lat': dest_lat, 'lon': dest_lon}})
    else:
        return jsonify({'status': 'error', 'message': 'Nie udało się wyznaczyć trasy'}), 500

@api_bp.route('/toilets', methods=['POST'])
def add_toilet():
    """Adds a new toilet."""
    data = request.json
    # Basic validation
    required = ['lat', 'lon', 'description', 'rating']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check for hate speech in description and name
    description = data.get('description', '')
    place_name = data.get('name', '') # Frontend sends 'name' mapped from place_name input
    
    if is_hate_speech(description) or is_hate_speech(place_name):
         return jsonify({'error': 'Opis lub nazwa zawiera niedozwolone treści (mowa nienawiści).'}), 400
        
    toilet_id = db.add_toilet(data)
    if toilet_id:
        return jsonify({'status': 'success', 'id': toilet_id})
    else:
        return jsonify({'error': 'Database error'}), 500

@api_bp.route('/comments', methods=['POST'])
def add_comment():
    data = request.json
    toilet_id = data.get('toilet_id')
    comment_text = data.get('comment')
    rating = data.get('rating')
    
    if not all([toilet_id, comment_text, rating]):
        return jsonify({'error': 'Missing fields'}), 400
        
    # Check for hate speech
    if is_hate_speech(comment_text):
        return jsonify({'error': 'Treść komentarza narusza zasady społeczności'}), 400
        
    success = db.add_comment(toilet_id, comment_text, rating)
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Database error'}), 500
