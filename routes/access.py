from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models import AccessRequest, User

access_bp = Blueprint('access', __name__)

@access_bp.route('/request', methods=['POST'])
def create_access_request():
    """Public endpoint for requesting access from landing page"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['name', 'email', 'company', 'role']
        for field in required:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if email already requested
        existing = AccessRequest.query.filter_by(email=data['email']).first()
        if existing:
            return jsonify({'message': 'Access request already submitted'}), 200
        
        # Create request
        access_request = AccessRequest(
            name=data['name'].strip(),
            email=data['email'].strip().lower(),
            company=data['company'].strip(),
            role=data['role'].strip(),
            drydock_date=data.get('drydock_date', '').strip() if data.get('drydock_date') else None,
            ready_to_test=data.get('ready_to_test', False),
            message=data.get('message', '').strip() if data.get('message') else None
        )
        
        db.session.add(access_request)
        db.session.commit()
        
        # TODO: Send email notification to admin
        
        return jsonify({
            'message': 'Access request submitted successfully',
            'id': access_request.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@access_bp.route('/requests', methods=['GET'])
@jwt_required()
def get_access_requests():
    """Get all access requests (admin only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        # Only admin can view requests
        if current_user.username != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        status = request.args.get('status')
        
        query = AccessRequest.query
        if status:
            query = query.filter_by(status=status)
        
        requests = query.order_by(AccessRequest.created_at.desc()).all()
        
        return jsonify([r.to_dict() for r in requests]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@access_bp.route('/requests/<int:request_id>', methods=['PUT'])
@jwt_required()
def update_access_request(request_id):
    """Update access request status (admin only)"""
    try:
        from datetime import datetime
        
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.username != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        access_request = AccessRequest.query.get(request_id)
        if not access_request:
            return jsonify({'error': 'Request not found'}), 404
        
        data = request.get_json()
        
        if 'status' in data:
            access_request.status = data['status']
            access_request.reviewed_at = datetime.utcnow()
            access_request.reviewed_by = user_id
        
        if 'notes' in data:
            access_request.notes = data['notes']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Request updated successfully',
            'request': access_request.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500