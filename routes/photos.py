from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
import cloudinary
import cloudinary.uploader
import cloudinary.api
from werkzeug.utils import secure_filename
import os
from app import db
from models import Photo, Penetration, User

photos_bp = Blueprint('photos', __name__)

# Configure Cloudinary (reads from environment variables)
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@photos_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_photo():
    """Upload photo to Cloudinary and create database record"""
    try:
        user_id = int(get_jwt_identity())
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, heic'}), 400
        
        penetration_id = request.form.get('penetration_id')
        if not penetration_id:
            return jsonify({'error': 'Penetration ID required'}), 400
        
        penetration = Penetration.query.get(penetration_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        photo_type = request.form.get('photo_type', 'general')
        caption = request.form.get('caption')
        
        # Upload to Cloudinary
        # Organize by penetration ID for better management
        upload_result = cloudinary.uploader.upload(
            file,
            folder=f"penlog/pen_{penetration_id}",
            resource_type="image",
            transformation=[
                {'width': 1920, 'height': 1080, 'crop': 'limit'},  # Max size
                {'quality': 'auto:good'}  # Auto optimize quality
            ]
        )
        
        # Create database record
        photo = Photo(
            penetration_id=penetration_id,
            user_id=user_id,
            filename=secure_filename(file.filename),
            filepath=upload_result['secure_url'],  # Store Cloudinary URL
            cloudinary_public_id=upload_result['public_id'],  # For deletion
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
        print(f"Photo upload error: {str(e)}")
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

@photos_bp.route('/<int:photo_id>', methods=['GET'])
def get_photo(photo_id):
    """Redirect to Cloudinary URL - public endpoint"""
    try:
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        # Redirect to Cloudinary URL
        return redirect(photo.filepath)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@photos_bp.route('/<int:photo_id>', methods=['DELETE'])
@jwt_required()
def delete_photo(photo_id):
    """Delete photo from Cloudinary and database"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        # Only photo uploader or supervisor/admin can delete
        if photo.user_id != user_id and current_user.role not in ['supervisor', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete from Cloudinary
        try:
            if hasattr(photo, 'cloudinary_public_id') and photo.cloudinary_public_id:
                cloudinary.uploader.destroy(photo.cloudinary_public_id)
        except Exception as e:
            print(f"Cloudinary deletion error: {str(e)}")
            # Continue even if Cloudinary delete fails
        
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