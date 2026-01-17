from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
import os
from functools import wraps
from app.models.database import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Hardcoded default or from env
        admin_user = os.environ.get('ADMIN_USER', 'admin')
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin')

        if username == admin_user and password == admin_pass:
            session['admin_logged_in'] = True
            return redirect(url_for('admin.dashboard'))
        else:
            return render_template('login.html', error="Nieprawidłowy login lub hasło")
            
    return render_template('login.html')

@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@login_required
def dashboard():
    return render_template('admin.html')

# --- Admin API Endpoints ---

@admin_bp.route('/api/toilets/<int:toilet_id>', methods=['DELETE'])
@login_required
def delete_toilet(toilet_id):
    success = db.delete_toilet(toilet_id)
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Failed to delete'}), 500

@admin_bp.route('/api/toilets/<int:toilet_id>', methods=['PUT'])
@login_required
def update_toilet(toilet_id):
    data = request.json
    success = db.update_toilet(toilet_id, data)
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Failed to update'}), 500

