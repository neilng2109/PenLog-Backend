from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models import Contractor, User

contractors_bp = Blueprint('contractors', __name__)

@contractors_bp.route('/', methods=['GET'])
@jwt_required()
def get_contractors():
    """Get all contractors"""
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        if active_only:
            contractors = Contractor.query.filter_by(active=True).all()
        else:
            contractors = Contractor.query.all()
        
        return jsonify([contractor.to_dict() for contractor in contractors]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/<int:contractor_id>', methods=['GET'])
@jwt_required()
def get_contractor(contractor_id):
    """Get single contractor"""
    try:
        contractor = Contractor.query.get(contractor_id)
        if not contractor:
            return jsonify({'error': 'Contractor not found'}), 404
        
        return jsonify(contractor.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/', methods=['POST'])
@jwt_required()
def create_contractor():
    """Create new contractor (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'error': 'Contractor name required'}), 400
        
        # Check if contractor already exists
        if Contractor.query.filter_by(name=data['name']).first():
            return jsonify({'error': 'Contractor already exists'}), 400
        
        contractor = Contractor(
            name=data['name'],
            contact_person=data.get('contact_person'),
            contact_email=data.get('contact_email'),
            contact_phone=data.get('contact_phone'),
            active=data.get('active', True)
        )
        
        db.session.add(contractor)
        db.session.commit()
        
        return jsonify({
            'message': 'Contractor created successfully',
            'contractor': contractor.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/<int:contractor_id>', methods=['PUT'])
@jwt_required()
def update_contractor(contractor_id):
    """Update contractor (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        contractor = Contractor.query.get(contractor_id)
        if not contractor:
            return jsonify({'error': 'Contractor not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        allowed_fields = ['name', 'contact_person', 'contact_email', 'contact_phone', 'active']
        for field in allowed_fields:
            if field in data:
                setattr(contractor, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Contractor updated successfully',
            'contractor': contractor.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/<int:contractor_id>/stats', methods=['GET'])
@jwt_required()
def get_contractor_stats(contractor_id):
    """Get statistics for a contractor"""
    try:
        contractor = Contractor.query.get(contractor_id)
        if not contractor:
            return jsonify({'error': 'Contractor not found'}), 404
        
        from sqlalchemy import func
        from models import Penetration
        
        # Count penetrations by status
        stats = db.session.query(
            Penetration.status,
            func.count(Penetration.id)
        ).filter_by(contractor_id=contractor_id).group_by(Penetration.status).all()
        
        status_counts = {status: count for status, count in stats}
        total = sum(status_counts.values())
        
        return jsonify({
            'contractor': contractor.to_dict(),
            'total_penetrations': total,
            'status_breakdown': status_counts,
            'completion_rate': round((status_counts.get('verified', 0) / total * 100), 2) if total > 0 else 0
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/<int:contractor_id>/generate-link', methods=['POST'])
@jwt_required()
def generate_access_link(contractor_id):
    """Generate magic link for contractor (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        contractor = Contractor.query.get(contractor_id)
        if not contractor:
            return jsonify({'error': 'Contractor not found'}), 404
        
        data = request.get_json()
        project_id = data.get('project_id')
        
        if not project_id:
            return jsonify({'error': 'Project ID required'}), 400
        
        from models import Project, ContractorAccessToken
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check if token already exists for this contractor/project
        existing_token = ContractorAccessToken.query.filter_by(
            project_id=project_id,
            contractor_id=contractor_id,
            active=True
        ).first()
        
        if existing_token:
            return jsonify({
                'message': 'Access link already exists',
                'access_token': existing_token.to_dict()
            }), 200
        
        # Generate new token
        token = ContractorAccessToken(
            project_id=project_id,
            contractor_id=contractor_id,
            token=ContractorAccessToken.generate_token(),
            active=True,
            expires_at=project.embarkation_date
        )
        
        db.session.add(token)
        db.session.commit()
        
        return jsonify({
            'message': 'Access link generated successfully',
            'access_token': token.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/merge', methods=['POST'])
@jwt_required()
def merge_contractors():
    """Merge two contractors (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        source_id = data.get('source_contractor_id')
        target_id = data.get('target_contractor_id')
        
        if not source_id or not target_id:
            return jsonify({'error': 'Both source and target contractor IDs required'}), 400
        
        if source_id == target_id:
            return jsonify({'error': 'Cannot merge contractor with itself'}), 400
        
        source = Contractor.query.get(source_id)
        target = Contractor.query.get(target_id)
        
        if not source or not target:
            return jsonify({'error': 'Contractor not found'}), 404
        
        from models import Penetration
        
        # Move all penetrations from source to target
        Penetration.query.filter_by(contractor_id=source_id).update({'contractor_id': target_id})
        
        # Move all users from source to target
        User.query.filter_by(contractor_id=source_id).update({'contractor_id': target_id})
        
        # Move all access tokens from source to target
        from models import ContractorAccessToken
        ContractorAccessToken.query.filter_by(contractor_id=source_id).update({'contractor_id': target_id})
        
        # Delete source contractor
        db.session.delete(source)
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully merged {source.name} into {target.name}',
            'contractor': target.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/project/<int:project_id>/access-links', methods=['GET'])
@jwt_required()
def get_project_contractor_links(project_id):
    """Get all contractor access links for a project (supervisor only)"""
    try:
        from models import ContractorAccessToken
        
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get all active tokens for this project
        tokens = ContractorAccessToken.query.filter_by(
            project_id=project_id,
            active=True
        ).all()
        
        result = []
        for token in tokens:
            result.append({
                'contractor_id': token.contractor_id,
                'contractor_name': token.contractor.name,
                'token': token.token,
                'magic_link': f"{request.host_url}report/{token.token}",
                'last_used': token.last_used_at.isoformat() if token.last_used_at else None,
                'created_at': token.created_at.isoformat() if token.created_at else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@contractors_bp.route('/project/<int:project_id>/contractor/<int:contractor_id>/regenerate-link', methods=['POST'])
@jwt_required()
def regenerate_magic_link(project_id, contractor_id):
    """Regenerate magic link for a contractor (supervisor only)"""
    try:
        from models import ContractorAccessToken
        
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Deactivate old token
        old_token = ContractorAccessToken.query.filter_by(
            project_id=project_id,
            contractor_id=contractor_id,
            active=True
        ).first()
        
        if old_token:
            old_token.active = False
        
        # Create new token
        new_token = ContractorAccessToken(
            project_id=project_id,
            contractor_id=contractor_id,
            token=ContractorAccessToken.generate_token(),
            active=True
        )
        
        db.session.add(new_token)
        db.session.commit()
        
        return jsonify({
            'message': 'Magic link regenerated successfully',
            'token': new_token.token,
            'magic_link': f"{request.host_url}report/{new_token.token}"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500