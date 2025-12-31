from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models import Penetration, PenActivity, User

penetrations_bp = Blueprint('penetrations', __name__)

@penetrations_bp.route('/', methods=['GET'])
@jwt_required()
def get_penetrations():
    """Get all penetrations with optional filtering"""
    try:
        # Get query parameters
        project_id = request.args.get('project_id')
        status = request.args.get('status')
        contractor_id = request.args.get('contractor_id')
        deck = request.args.get('deck')
        priority = request.args.get('priority')
        
        # Build query
        query = Penetration.query
        
        # Project filter is required for most queries
        if project_id:
            query = query.filter_by(project_id=project_id)
        
        if status:
            query = query.filter_by(status=status)
        if contractor_id:
            query = query.filter_by(contractor_id=contractor_id)
        if deck:
            query = query.filter_by(deck=deck)
        if priority:
            query = query.filter_by(priority=priority)
        
        penetrations = query.all()
        return jsonify([pen.to_dict() for pen in penetrations]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@penetrations_bp.route('/<int:pen_id>', methods=['GET'])
@jwt_required()
def get_penetration(pen_id):
    """Get single penetration with activities and photos"""
    try:
        penetration = Penetration.query.get(pen_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        return jsonify(penetration.to_dict(include_activities=True, include_photos=True)), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@penetrations_bp.route('/', methods=['POST'])
@jwt_required()
def create_penetration():
    """Create new penetration (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['project_id', 'pen_id', 'deck']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if pen_id already exists for this contractor in this project
        existing = Penetration.query.filter_by(
            project_id=data['project_id'],
            contractor_id=data.get('contractor_id'),
            pen_id=data['pen_id']
        ).first()
        
        if existing:
            contractor_name = existing.contractor.name if existing.contractor else 'this contractor'
            return jsonify({'error': f"Pen {data['pen_id']} already exists for {contractor_name} in this project"}), 400
        
        penetration = Penetration(
            project_id=data['project_id'],
            pen_id=data['pen_id'],
            deck=data['deck'],
            fire_zone=data.get('fire_zone'),
            frame=data.get('frame'),
            location=data.get('location'),
            pen_type=data.get('pen_type'),
            size=data.get('size'),
            contractor_id=data.get('contractor_id'),
            priority=data.get('priority', 'routine'),
            notes=data.get('notes')
        )
        
        db.session.add(penetration)
        db.session.commit()
        
        return jsonify({
            'message': 'Penetration created successfully',
            'penetration': penetration.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@penetrations_bp.route('/<int:pen_id>', methods=['PUT'])
@jwt_required()
def update_penetration(pen_id):
    """Update penetration details"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        penetration = Penetration.query.get(pen_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        data = request.get_json()
        
        # Only supervisor can change certain fields
        supervisor_only_fields = ['pen_id', 'contractor_id', 'priority']
        if current_user.role != 'supervisor':
            if any(field in data for field in supervisor_only_fields):
                return jsonify({'error': 'Unauthorized to modify these fields'}), 403
        
        # Update fields
        allowed_fields = ['deck', 'location', 'pen_type', 'size', 'contractor_id', 'priority', 'notes']
        for field in allowed_fields:
            if field in data:
                setattr(penetration, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Penetration updated successfully',
            'penetration': penetration.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@penetrations_bp.route('/<int:pen_id>/status', methods=['POST'])
@jwt_required()
def update_status(pen_id):
    """Update penetration status and log activity"""
    try:
        from datetime import datetime
        
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        penetration = Penetration.query.get(pen_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        notes = data.get('notes')
        
        if not new_status:
            return jsonify({'error': 'Status required'}), 400
        
        valid_statuses = ['not_started', 'open', 'closed', 'verified']
        if new_status not in valid_statuses:
            return jsonify({'error': 'Invalid status'}), 400
        
        # Validate photo count when closing
        if new_status == 'closed':
            photo_count = penetration.photos.count()
            if photo_count < 2:
                return jsonify({
                    'error': f'Cannot close: Only {photo_count} photo(s) attached. Minimum 2 photos required.',
                    'photo_count': photo_count,
                    'requires_photos': True
                }), 400
        
        # Check authorization for status changes
        if current_user.role == 'contractor':
            # Contractors can only open/close their own penetrations
            if penetration.contractor_id != current_user.contractor_id:
                return jsonify({'error': 'Unauthorized'}), 403
            if new_status == 'verified':
                return jsonify({'error': 'Only supervisors can verify'}), 403
        
        previous_status = penetration.status
        
        # Log activity (even if status unchanged, to record notes)
        activity = PenActivity(
            penetration_id=pen_id,
            user_id=user_id,
            action=f"status_changed" if new_status != previous_status else "note_added",
            previous_status=previous_status,
            new_status=new_status,
            notes=notes
        )
        
        # Update status
        penetration.status = new_status
        
        # Automatically set timestamps based on status
        if new_status == 'open' and not penetration.opened_at:
            penetration.opened_at = datetime.utcnow()
        elif new_status in ['closed', 'verified'] and not penetration.completed_at:
            penetration.completed_at = datetime.utcnow()
        
        # If going back to open from closed, clear completed_at
        if new_status == 'open' and previous_status in ['closed', 'verified']:
            penetration.completed_at = None
        
        # If going back to not_started, clear both timestamps
        if new_status == 'not_started':
            penetration.opened_at = None
            penetration.completed_at = None
        
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({
            'message': 'Status updated successfully',
            'penetration': penetration.to_dict(),
            'activity': activity.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@penetrations_bp.route('/<int:pen_id>/activities', methods=['GET'])
@jwt_required()
def get_activities(pen_id):
    """Get all activities for a penetration"""
    try:
        penetration = Penetration.query.get(pen_id)
        if not penetration:
            return jsonify({'error': 'Penetration not found'}), 404
        
        activities = PenActivity.query.filter_by(penetration_id=pen_id)\
            .order_by(PenActivity.timestamp.desc()).all()
        
        return jsonify([activity.to_dict() for activity in activities]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@penetrations_bp.route('/bulk-import', methods=['POST'])
@jwt_required()
def bulk_import():
    """Bulk import penetrations from spreadsheet (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        project_id = data.get('project_id')
        penetrations_data = data.get('penetrations', [])
        
        if not project_id:
            return jsonify({'error': 'Project ID required'}), 400
        
        if not penetrations_data:
            return jsonify({'error': 'No penetrations provided'}), 400
        
        # Verify project exists
        from models import Project
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        created = []
        errors = []
        
        for pen_data in penetrations_data:
            try:
                # Check if already exists in this project
                existing = Penetration.query.filter_by(
                    project_id=project_id,
                    pen_id=pen_data['pen_id']
                ).first()
                
                if existing:
                    errors.append(f"{pen_data['pen_id']}: Already exists in this project")
                    continue
                
                penetration = Penetration(
                    project_id=project_id,
                    pen_id=pen_data['pen_id'],
                    deck=pen_data['deck'],
                    fire_zone=pen_data.get('fire_zone'),
                    frame=pen_data.get('frame'),
                    location=pen_data.get('location'),
                    pen_type=pen_data.get('pen_type'),
                    size=pen_data.get('size'),
                    contractor_id=pen_data.get('contractor_id'),
                    priority=pen_data.get('priority', 'routine'),
                    status=pen_data.get('status', 'not_started')
                )
                
                db.session.add(penetration)
                created.append(pen_data['pen_id'])
                
            except Exception as e:
                errors.append(f"{pen_data.get('pen_id', 'unknown')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'message': f'Imported {len(created)} penetrations',
            'created': created,
            'errors': errors
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500