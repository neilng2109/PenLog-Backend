from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from app import db
from models import Project, ContractorRegistration, Contractor, User, ContractorAccessToken

registration_bp = Blueprint('registration', __name__)

@registration_bp.route('/join/<invite_code>', methods=['GET'])
def get_registration_form(invite_code):
    """Get project details for registration (public endpoint)"""
    try:
        # For now, invite_code is just the project_id
        # In production, you'd have a separate invite codes table
        project_id = int(invite_code)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Invalid invitation code'}), 404
        
        if project.status != 'active':
            return jsonify({'error': 'This drydock is no longer active'}), 400
        
        return jsonify({
            'project': {
                'id': project.id,
                'name': project.name,
                'ship_name': project.ship_name,
                'drydock_location': project.drydock_location
            }
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid invitation code'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@registration_bp.route('/join/<invite_code>', methods=['POST'])
def submit_registration(invite_code):
    """Submit contractor registration (public endpoint)"""
    try:
        project_id = int(invite_code)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Invalid invitation code'}), 404
        
        if project.status != 'active':
            return jsonify({'error': 'This drydock is no longer active'}), 400
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['company_name', 'contact_person', 'contact_email']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if already registered
        existing = ContractorRegistration.query.filter_by(
            project_id=project_id,
            contact_email=data['contact_email'],
            status='pending'
        ).first()
        
        if existing:
            return jsonify({'error': 'Registration already submitted'}), 400
        
        # Create registration
        registration = ContractorRegistration(
            project_id=project_id,
            company_name=data['company_name'].strip(),
            contact_person=data['contact_person'].strip(),
            contact_email=data['contact_email'].strip().lower(),
            status='pending'
        )
        
        db.session.add(registration)
        db.session.commit()
        
        return jsonify({
            'message': 'Registration submitted successfully',
            'registration': registration.to_dict()
        }), 201
        
    except ValueError:
        return jsonify({'error': 'Invalid invitation code'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@registration_bp.route('/pending', methods=['GET'])
@jwt_required()
def get_pending_registrations():
    """Get pending registrations (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        project_id = request.args.get('project_id')
        
        query = ContractorRegistration.query.filter_by(status='pending')
        
        if project_id:
            query = query.filter_by(project_id=project_id)
        
        registrations = query.order_by(ContractorRegistration.created_at.desc()).all()
        
        return jsonify([r.to_dict() for r in registrations]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@registration_bp.route('/<int:registration_id>/approve', methods=['POST'])
@jwt_required()
def approve_registration(registration_id):
    """Approve contractor registration and generate access token (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        registration = ContractorRegistration.query.get(registration_id)
        if not registration:
            return jsonify({'error': 'Registration not found'}), 404
        
        if registration.status != 'pending':
            return jsonify({'error': 'Registration already processed'}), 400
        
        data = request.get_json() or {}
        
        # Allow supervisor to edit company name before approving
        company_name = data.get('company_name', registration.company_name).strip()
        
        # Check if contractor already exists
        contractor = Contractor.query.filter_by(name=company_name).first()
        
        if not contractor:
            # Create new contractor
            contractor = Contractor(
                name=company_name,
                contact_person=registration.contact_person,
                contact_email=registration.contact_email,
                active=True
            )
            db.session.add(contractor)
            db.session.flush()  # Get contractor ID
        
        # Link contractor to project if not already linked
        project = Project.query.get(registration.project_id)
        if contractor not in project.contractors:
            project.contractors.append(contractor)
        
        # Generate access token
        token = ContractorAccessToken(
            project_id=registration.project_id,
            contractor_id=contractor.id,
            token=ContractorAccessToken.generate_token(),
            active=True,
            expires_at=project.embarkation_date  # Token expires when drydock ends
        )
        db.session.add(token)
        
        # Update registration status
        registration.status = 'approved'
        registration.reviewed_at = datetime.utcnow()
        registration.reviewed_by = user_id
        
        db.session.commit()
        
        return jsonify({
            'message': 'Registration approved successfully',
            'contractor': contractor.to_dict(),
            'access_token': token.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@registration_bp.route('/<int:registration_id>/reject', methods=['POST'])
@jwt_required()
def reject_registration(registration_id):
    """Reject contractor registration (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        registration = ContractorRegistration.query.get(registration_id)
        if not registration:
            return jsonify({'error': 'Registration not found'}), 404
        
        if registration.status != 'pending':
            return jsonify({'error': 'Registration already processed'}), 400
        
        data = request.get_json() or {}
        
        registration.status = 'rejected'
        registration.rejection_reason = data.get('reason', 'No reason provided')
        registration.reviewed_at = datetime.utcnow()
        registration.reviewed_by = user_id
        
        db.session.commit()
        
        return jsonify({
            'message': 'Registration rejected',
            'registration': registration.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500