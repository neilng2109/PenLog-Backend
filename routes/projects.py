from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from app import db
from models import Project, User
from sqlalchemy import func, case

projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/', methods=['GET'])
@jwt_required()
def get_projects():
    """Get all projects"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        status = request.args.get('status')
        include_stats = request.args.get('include_stats', 'false').lower() == 'true'
        
        query = Project.query
        
        # Filter by supervisor - admins see all, supervisors see only their projects
        if current_user.username == 'admin':
            # Admin sees all projects
            pass
        else:
            # Supervisors see only their assigned projects
            query = query.filter_by(supervisor_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        projects = query.order_by(Project.start_date.desc()).all()
        
        return jsonify([p.to_dict(include_stats=include_stats) for p in projects]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    """Get single project with stats"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check if user has access to this project
        if current_user.username != 'admin' and project.supervisor_id != user_id:
            return jsonify({'error': 'Unauthorized - You are not assigned to this project'}), 403
        
        return jsonify(project.to_dict(include_stats=True)), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/', methods=['POST'])
@jwt_required()
def create_project():
    """Create new project (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'ship_name', 'drydock_location', 'start_date', 'embarkation_date']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Parse dates
        try:
            start_date = datetime.fromisoformat(data['start_date']).date()
            embarkation_date = datetime.fromisoformat(data['embarkation_date']).date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}), 400
        
        project = Project(
            name=data['name'],
            ship_name=data['ship_name'],
            drydock_location=data['drydock_location'],
            start_date=start_date,
            embarkation_date=embarkation_date,
            status=data.get('status', 'active'),
            notes=data.get('notes')
        )
        
        db.session.add(project)
        db.session.commit()
        
        return jsonify({
            'message': 'Project created successfully',
            'project': project.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>', methods=['PUT'])
@jwt_required()
def update_project(project_id):
    """Update project (supervisor only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            project.name = data['name']
        if 'ship_name' in data:
            project.ship_name = data['ship_name']
        if 'drydock_location' in data:
            project.drydock_location = data['drydock_location']
        if 'start_date' in data:
            try:
                project.start_date = datetime.fromisoformat(data['start_date']).date()
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400
        if 'embarkation_date' in data:
            try:
                project.embarkation_date = datetime.fromisoformat(data['embarkation_date']).date()
            except ValueError:
                return jsonify({'error': 'Invalid embarkation_date format'}), 400
        if 'status' in data:
            project.status = data['status']
        if 'notes' in data:
            project.notes = data['notes']
        
        # Prepare response data before commit
        project_dict = project.to_dict()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Project updated successfully',
            'project': project_dict
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@jwt_required()
def delete_project(project_id):
    """Delete project (supervisor only) - WARNING: Deletes all penetrations"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({'message': 'Project deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/assign-supervisor', methods=['PUT'])
@jwt_required()
def assign_supervisor(project_id):
    """Assign a supervisor to a project (admin only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        # Only admin can assign supervisors
        if current_user.username != 'admin':
            return jsonify({'error': 'Unauthorized - Admin only'}), 403
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        supervisor_id = data.get('supervisor_id')
        
        if not supervisor_id:
            return jsonify({'error': 'supervisor_id is required'}), 400
        
        # Verify supervisor exists and is a supervisor role
        supervisor = User.query.get(supervisor_id)
        if not supervisor:
            return jsonify({'error': 'Supervisor user not found'}), 404
        
        if supervisor.role != 'supervisor':
            return jsonify({'error': 'User is not a supervisor'}), 400
        
        # Assign supervisor
        project.supervisor_id = supervisor_id
        db.session.commit()
        
        return jsonify({
            'message': 'Supervisor assigned successfully',
            'project': project.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/supervisors', methods=['GET'])
@jwt_required()
def get_supervisors():
    """Get all supervisor users (admin only)"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        # Only admin can see all supervisors
        if current_user.username != 'admin':
            return jsonify({'error': 'Unauthorized - Admin only'}), 403
        
        supervisors = User.query.filter_by(role='supervisor').all()
        
        return jsonify([{
            'id': s.id,
            'username': s.username,
            'email': s.email
        } for s in supervisors]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({'message': 'Project deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/dashboard', methods=['GET'])
@jwt_required()
def get_project_dashboard(project_id):
    """Get comprehensive dashboard data for a project"""
    try:
        from sqlalchemy import func
        from models import Penetration, Contractor
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Overall stats
        total = project.penetrations.count()
        not_started = project.penetrations.filter_by(status='not_started').count()
        open_count = project.penetrations.filter_by(status='open').count()
        closed = project.penetrations.filter_by(status='closed').count()
        verified = project.penetrations.filter_by(status='verified').count()
        
        # Count pens without photos (or with less than 2 photos)
        from models import Photo
        pens_with_insufficient_photos = db.session.query(Penetration.id).outerjoin(Photo).group_by(
            Penetration.id
        ).having(
            func.count(Photo.id) < 2
        ).filter(
            Penetration.project_id == project_id,
            Penetration.status.in_(['open', 'closed'])  # Only check active pens
        ).count()
        
       # By contractor - aggregate all statuses
        contractor_stats = db.session.query(
            Contractor.id,
            Contractor.name,
            func.count(Penetration.id).label('total'),
            func.sum(case((Penetration.status == 'verified', 1), else_=0)).label('verified'),
            func.sum(case((Penetration.status == 'closed', 1), else_=0)).label('closed'),
            func.sum(case((Penetration.status == 'open', 1), else_=0)).label('open'),
            func.sum(case((Penetration.status == 'not_started', 1), else_=0)).label('not_started')
        ).join(Penetration, Contractor.id == Penetration.contractor_id).filter(
            Penetration.project_id == project_id
        ).group_by(
            Contractor.id,
            Contractor.name
        ).all()

        # Build contractor data
        contractor_data = []
        for stat in contractor_stats:
            completion_rate = round((stat.verified / stat.total * 100), 2) if stat.total > 0 else 0
            contractor_data.append({
                'id': stat.id,
                'name': stat.name,
                'total': stat.total,
                'not_started': stat.not_started,
                'open': stat.open,
                'closed': stat.closed,
                'verified': stat.verified,
                'completion_rate': completion_rate
            })
        
                
        # By deck
        deck_stats = db.session.query(
            Penetration.deck,
            Penetration.status,
            func.count(Penetration.id).label('count')
        ).filter(
            Penetration.project_id == project_id
        ).group_by(
            Penetration.deck,
            Penetration.status
        ).all()
        
        # Organize deck data
        deck_data = {}
        for deck, status, count in deck_stats:
            if deck not in deck_data:
                deck_data[deck] = {
                    'deck': deck,
                    'total': 0,
                    'not_started': 0,
                    'open': 0,
                    'closed': 0,
                    'verified': 0
                }
            
            deck_data[deck][status] = count
            deck_data[deck]['total'] += count
        
        return jsonify({
            'project': project.to_dict(),
            'overall': {
                'total': total,
                'not_started': not_started,
                'open': open_count,
                'closed': closed,
                'verified': verified,
                'completion_rate': round((verified / total * 100), 2) if total > 0 else 0,
                'pens_without_photos': pens_with_insufficient_photos
            },
            'by_contractor': contractor_data,
            'by_deck': list(deck_data.values())
        }), 200
               
    except Exception as e:  # ADD THIS
        return jsonify({'error': str(e)}), 500  # ADD THIS
        
        
        # Add this endpoint to routes/projects.py

@projects_bp.route('/<int:project_id>/invite-code', methods=['POST'])
@jwt_required()
def generate_invite_code(project_id):
    """Generate or regenerate invite code for contractor registration"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        # Only supervisors/admins can generate invite codes
        if current_user.role not in ['supervisor', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Generate new invite code
        invite_code = project.generate_invite_code()
        db.session.commit()
        
        return jsonify({
            'message': 'Invite code generated successfully',
            'invite_code': invite_code,
            'invite_url': f'https://app.penlog.io/join/{invite_code}'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<int:project_id>/invite-code', methods=['GET'])
@jwt_required()
def get_invite_code(project_id):
    """Get current invite code for a project"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        # Only supervisors/admins can view invite codes
        if current_user.role not in ['supervisor', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # If no invite code exists, generate one
        if not project.invite_code:
            project.generate_invite_code()
            db.session.commit()
        
        return jsonify({
            'invite_code': project.invite_code,
            'invite_url': f'https://app.penlog.io/join/{project.invite_code}'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500