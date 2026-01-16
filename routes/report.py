from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from models import ContractorAccessToken, Penetration, PenActivity, Photo, Project, Contractor
import os
from werkzeug.utils import secure_filename

report_bp = Blueprint('report', __name__)

@report_bp.route('/<token>', methods=['GET'])
def get_contractor_form(token):
    """Get contractor reporting form (public, no auth required)"""
    try:
        access_token = ContractorAccessToken.query.filter_by(token=token).first()
        
        if not access_token:
            return jsonify({'error': 'Invalid access link'}), 404
        
        if not access_token.is_valid():
            return jsonify({'error': 'Access link has expired or been revoked'}), 403
        
        # Update last used timestamp
        access_token.last_used_at = datetime.utcnow()
        db.session.commit()
        
        # Get project and contractor info
        project = Project.query.get(access_token.project_id)
        contractor = access_token.contractor
        
        # Get penetrations for this contractor
        penetrations = Penetration.query.filter_by(
            project_id=access_token.project_id,
            contractor_id=access_token.contractor_id
        ).all()
        
        return jsonify({
            'project': {
                'id': project.id,
                'name': project.name,
                'ship_name': project.ship_name,
                'drydock_location': project.drydock_location
            },
            'contractor': {
                'id': contractor.id,
                'name': contractor.name
            },
            'penetrations': [p.to_dict() for p in penetrations]
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@report_bp.route('/<token>/create-pen', methods=['POST'])
def create_pen_via_token(token):
    """Create a new pen via contractor access token"""
    try:
        access_token = ContractorAccessToken.query.filter_by(token=token).first()
        
        if not access_token or not access_token.is_valid():
            return jsonify({'error': 'Invalid or expired access link'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required = ['pen_id', 'deck', 'location']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields: pen_id, deck, location'}), 400
        
        # Check for duplicate pen_id for this contractor
        existing = Penetration.query.filter_by(
            project_id=access_token.project_id,
            contractor_id=access_token.contractor_id,
            pen_id=data['pen_id']
        ).first()
        
        if existing:
            return jsonify({'error': f"Pen {data['pen_id']} already exists"}), 400
        
        # Create new penetration
        pen = Penetration(
            project_id=access_token.project_id,
            contractor_id=access_token.contractor_id,
            pen_id=data['pen_id'],
            deck=data['deck'],
            location=data['location'],
            fire_zone=data.get('fire_zone'),
            frame=data.get('frame'),
            pen_type=data.get('pen_type'),
            status='not_started'
        )
        
        db.session.add(pen)
        db.session.commit()
        
        return jsonify(pen.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@report_bp.route('/<token>/submit', methods=['POST'])
def submit_contractor_report(token):
    """Submit penetration status update (public, no auth required)"""
    try:
        access_token = ContractorAccessToken.query.filter_by(token=token).first()
        
        if not access_token:
            return jsonify({'error': 'Invalid access link'}), 404
        
        if not access_token.is_valid():
            return jsonify({'error': 'Access link has expired or been revoked'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('pen_id'):
            return jsonify({'error': 'Penetration ID required'}), 400
        
        if not data.get('action') or data['action'] not in ['open', 'close']:
            return jsonify({'error': 'Invalid action. Must be "open" or "close"'}), 400
        
        # Find penetration by database ID (not pen_id string)
        penetration = Penetration.query.get(data['pen_id'])
        
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        # Verify this contractor is assigned to this pen
        if penetration.contractor_id != access_token.contractor_id:
            return jsonify({'error': 'You are not assigned to this penetration'}), 403
        
        # ========== ADD THIS VALIDATION BLOCK ==========
        # Validate photo count when closing
        if data['action'] == 'close':
            photo_count = penetration.photos.count()
            if photo_count < 2:
                return jsonify({
                    'error': f'Cannot close: Only {photo_count} photo(s) attached. Minimum 2 photos required.',
                    'photo_count': photo_count,
                    'requires_photos': True
                }), 400
        # ========== END NEW VALIDATION ==========
        
        # Update status based on action
        previous_status = penetration.status
        
        if data['action'] == 'open':
            penetration.status = 'open'
            penetration.opened_at = datetime.utcnow()
        elif data['action'] == 'close':
            penetration.status = 'closed'
            penetration.completed_at = datetime.utcnow()
        
        # Log activity with contractor name (no user_id since this is public access)
        # Store contractor info in notes field for attribution
        contractor = access_token.contractor
        activity_notes = data.get('notes', '')
        
        activity = PenActivity(
            penetration_id=penetration.id,
            user_id=None,  # No user for magic link access
            action=data['action'],
            previous_status=previous_status,
            new_status=penetration.status,
            notes=activity_notes,
            contractor_name=contractor.name  # Add contractor attribution
        )
        
        db.session.add(activity)
        
        # Update last used timestamp
        access_token.last_used_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Report submitted successfully',
            'penetration': penetration.to_dict(),
            'activity': activity.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@report_bp.route('/<token>/upload', methods=['POST'])
def upload_contractor_photo(token):
    """Upload photo for penetration via Cloudinary (public, no auth required)"""
    try:
        import cloudinary
        import cloudinary.uploader
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
            secure=True
        )
        
        access_token = ContractorAccessToken.query.filter_by(token=token).first()
        
        if not access_token:
            return jsonify({'error': 'Invalid access link'}), 404
        
        if not access_token.is_valid():
            return jsonify({'error': 'Access link has expired or been revoked'}), 403
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
            return jsonify({'error': 'Invalid file type'}), 400
        
        penetration_id = request.form.get('penetration_id')
        if not penetration_id:
            return jsonify({'error': 'Penetration ID required'}), 400
        
        penetration = Penetration.query.get(penetration_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        if penetration.contractor_id != access_token.contractor_id:
            return jsonify({'error': 'You are not assigned to this penetration'}), 403
        
        photo_type = request.form.get('photo_type', 'general')
        caption = request.form.get('caption')
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder=f"penlog/pen_{penetration_id}",
            resource_type="image",
            transformation=[
                {'width': 1920, 'height': 1080, 'crop': 'limit'},
                {'quality': 'auto:good'}
            ]
        )
        
        # Create photo record
        photo = Photo(
            penetration_id=penetration_id,
            user_id=None,
            filename=secure_filename(file.filename),
            filepath=upload_result['secure_url'],  # Cloudinary URL
            cloudinary_public_id=upload_result['public_id'],
            caption=caption,
            photo_type=photo_type
        )
        
        db.session.add(photo)
        access_token.last_used_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Photo uploaded successfully',
            'photo': photo.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Photo upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500