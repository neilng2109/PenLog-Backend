import os
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from PIL import Image
from app import db
from models import Photo, Penetration, User
from datetime import datetime

photos_bp = Blueprint('photos', __name__)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def optimize_image(filepath, max_size=(1920, 1080), quality=85):
    """Optimize image size and quality"""
    try:
        img = Image.open(filepath)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Resize if larger than max_size
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save optimized image
        img.save(filepath, 'JPEG', quality=quality, optimize=True)
        
    except Exception as e:
        print(f"Error optimizing image: {e}")

@photos_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_photo():
    """Upload photo for a penetration"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Get additional data
        penetration_id = request.form.get('penetration_id')
        caption = request.form.get('caption')
        photo_type = request.form.get('photo_type', 'general')
        
        if not penetration_id:
            return jsonify({'error': 'Penetration ID required'}), 400
        
        # Verify penetration exists
        penetration = Penetration.query.get(penetration_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{penetration.pen_id}_{timestamp}_{name}{ext}"
        
        # Create upload directory if it doesn't exist
        upload_folder = current_app.config['UPLOAD_FOLDER']
        pen_folder = os.path.join(upload_folder, penetration.pen_id)
        os.makedirs(pen_folder, exist_ok=True)
        
        # Save file
        filepath = os.path.join(pen_folder, unique_filename)
        file.save(filepath)
        
        # Optimize image
        optimize_image(filepath)
        
        # Create photo record
        photo = Photo(
            penetration_id=penetration_id,
            user_id=user_id,
            filename=unique_filename,
            filepath=filepath,
            caption=caption,
            photo_type=photo_type
        )
        
        db.session.add(photo)
        db.session.commit()
        
        return jsonify({
            'message': 'Photo uploaded successfully',
            'photo': photo.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@photos_bp.route('/<int:photo_id>', methods=['GET'])
def get_photo(photo_id):
    """Get photo file - public endpoint for image display"""
    try:
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        if not os.path.exists(photo.filepath):
            return jsonify({'error': 'Photo file not found'}), 404
        
        return send_file(photo.filepath, mimetype='image/jpeg')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@photos_bp.route('/<int:photo_id>/info', methods=['GET'])
@jwt_required()
def get_photo_info(photo_id):
    """Get photo metadata"""
    try:
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        return jsonify(photo.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@photos_bp.route('/<int:photo_id>', methods=['DELETE'])
@jwt_required()
def delete_photo(photo_id):
    """Delete photo"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        # Only photo uploader or supervisor can delete
        if photo.user_id != user_id and current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete file from filesystem
        if os.path.exists(photo.filepath):
            os.remove(photo.filepath)
        
        # Delete database record
        db.session.delete(photo)
        db.session.commit()
        
        return jsonify({'message': 'Photo deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@photos_bp.route('/penetration/<int:penetration_id>', methods=['GET'])
@jwt_required()
def get_penetration_photos(penetration_id):
    """Get all photos for a penetration"""
    try:
        penetration = Penetration.query.get(penetration_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        photos = Photo.query.filter_by(penetration_id=penetration_id)\
            .order_by(Photo.uploaded_at.desc()).all()
        
        return jsonify([photo.to_dict() for photo in photos]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500