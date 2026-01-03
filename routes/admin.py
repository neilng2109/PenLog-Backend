from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from models import db
from models import AccessRequest, User
from werkzeug.security import generate_password_hash
import secrets
import string

admin_bp = Blueprint('admin', __name__)

def generate_temp_password(length=12):
    """Generate a secure temporary password"""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(chars) for _ in range(length))

@admin_bp.route('/access-requests', methods=['GET'])
@jwt_required()
def get_access_requests():
    """Get all access requests (admin/supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role not in ['supervisor', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        status = request.args.get('status', 'pending')
        
        query = AccessRequest.query
        if status:
            query = query.filter_by(status=status)
        
        requests = query.order_by(AccessRequest.created_at.desc()).all()
        
        return jsonify([r.to_dict() for r in requests]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/access-requests/<int:request_id>/approve', methods=['POST'])
@jwt_required()
def approve_access_request(request_id):
    """Approve access request and create user account"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role not in ['supervisor', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        access_request = AccessRequest.query.get(request_id)
        if not access_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if access_request.status != 'pending':
            return jsonify({'error': 'Request already processed'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=access_request.email).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 400
        
        # Generate temporary password
        temp_password = generate_temp_password()
        
        # Create user account
        new_user = User(
            username=access_request.email,
            email=access_request.email,
            password_hash=generate_password_hash(temp_password),
            role='supervisor'  # Default role for new users
        )
        
        db.session.add(new_user)
        
        # Update access request
        access_request.status = 'approved'
        access_request.reviewed_at = datetime.utcnow()
        access_request.reviewed_by = user_id
        
        db.session.commit()
        
        return jsonify({
            'message': 'Access request approved',
            'user': new_user.to_dict(),
            'temporary_password': temp_password,  # You'll want to email this
            'access_request': access_request.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/access-requests/<int:request_id>/reject', methods=['POST'])
@jwt_required()
def reject_access_request(request_id):
    """Reject access request"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role not in ['supervisor', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        access_request = AccessRequest.query.get(request_id)
        if not access_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if access_request.status != 'pending':
            return jsonify({'error': 'Request already processed'}), 400
        
        data = request.get_json() or {}
        
        access_request.status = 'rejected'
        access_request.rejection_reason = data.get('reason', 'No reason provided')
        access_request.reviewed_at = datetime.utcnow()
        access_request.reviewed_by = user_id
        
        db.session.commit()
        
        return jsonify({
            'message': 'Access request rejected',
            'access_request': access_request.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500