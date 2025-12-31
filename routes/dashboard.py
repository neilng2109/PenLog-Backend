from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from app import db
from models import Penetration, Contractor, PenActivity, User
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/overview', methods=['GET'])
@jwt_required()
def get_overview():
    """Get dashboard overview statistics"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        # Base query
        query = Penetration.query
        
        # If contractor user, filter to their penetrations only
        if current_user.role == 'contractor':
            query = query.filter_by(contractor_id=current_user.contractor_id)
        
        # Total counts by status
        total = query.count()
        not_started = query.filter_by(status='not_started').count()
        open_count = query.filter_by(status='open').count()
        closed = query.filter_by(status='closed').count()
        verified = query.filter_by(status='verified').count()
        
        # Calculate completion percentage
        completion_rate = round((verified / total * 100), 2) if total > 0 else 0
        
        # Count by priority
        critical = query.filter_by(priority='critical').count()
        important = query.filter_by(priority='important').count()
        routine = query.filter_by(priority='routine').count()
        
        # Recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_activities = PenActivity.query.filter(
            PenActivity.timestamp >= yesterday
        ).order_by(PenActivity.timestamp.desc()).limit(10).all()
        
        return jsonify({
            'total_penetrations': total,
            'status_breakdown': {
                'not_started': not_started,
                'open': open_count,
                'closed': closed,
                'verified': verified
            },
            'completion_rate': completion_rate,
            'priority_breakdown': {
                'critical': critical,
                'important': important,
                'routine': routine
            },
            'recent_activities': [activity.to_dict() for activity in recent_activities]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/by-contractor', methods=['GET'])
@jwt_required()
def get_by_contractor():
    """Get penetrations grouped by contractor"""
    try:
        user_id = int(get_jwt_identity())
        current_user = User.query.get(user_id)
        
        if current_user.role != 'supervisor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get all contractors with their penetration counts
        contractors_stats = db.session.query(
            Contractor.id,
            Contractor.name,
            Penetration.status,
            func.count(Penetration.id).label('count')
        ).outerjoin(Penetration).group_by(
            Contractor.id,
            Contractor.name,
            Penetration.status
        ).all()
        
        # Organize data by contractor
        contractor_data = {}
        for contractor_id, contractor_name, status, count in contractors_stats:
            if contractor_id not in contractor_data:
                contractor_data[contractor_id] = {
                    'id': contractor_id,
                    'name': contractor_name,
                    'total': 0,
                    'not_started': 0,
                    'open': 0,
                    'closed': 0,
                    'verified': 0,
                    'completion_rate': 0
                }
            
            if status:
                contractor_data[contractor_id][status] = count
                contractor_data[contractor_id]['total'] += count
        
        # Calculate completion rates
        for contractor_id in contractor_data:
            data = contractor_data[contractor_id]
            if data['total'] > 0:
                data['completion_rate'] = round((data['verified'] / data['total'] * 100), 2)
        
        return jsonify(list(contractor_data.values())), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/by-deck', methods=['GET'])
@jwt_required()
def get_by_deck():
    """Get penetrations grouped by deck"""
    try:
        # Get penetration counts by deck and status
        deck_stats = db.session.query(
            Penetration.deck,
            Penetration.status,
            func.count(Penetration.id).label('count')
        ).group_by(
            Penetration.deck,
            Penetration.status
        ).all()
        
        # Organize data by deck
        deck_data = {}
        for deck, status, count in deck_stats:
            if deck not in deck_data:
                deck_data[deck] = {
                    'deck': deck,
                    'total': 0,
                    'not_started': 0,
                    'open': 0,
                    'closed': 0,
                    'verified': 0,
                    'completion_rate': 0
                }
            
            deck_data[deck][status] = count
            deck_data[deck]['total'] += count
        
        # Calculate completion rates
        for deck in deck_data:
            data = deck_data[deck]
            if data['total'] > 0:
                data['completion_rate'] = round((data['verified'] / data['total'] * 100), 2)
        
        # Sort by deck name
        sorted_decks = sorted(deck_data.values(), key=lambda x: x['deck'])
        
        return jsonify(sorted_decks), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/open-too-long', methods=['GET'])
@jwt_required()
def get_open_too_long():
    """Get penetrations that have been open for too long"""
    try:
        # Define threshold (e.g., 48 hours)
        threshold_hours = int(request.args.get('hours', 48))
        threshold_time = datetime.utcnow() - timedelta(hours=threshold_hours)
        
        # Find penetrations opened before threshold and still open
        open_pens = Penetration.query.filter_by(status='open').all()
        
        flagged_pens = []
        for pen in open_pens:
            # Get last activity that opened this pen
            last_open = PenActivity.query.filter_by(
                penetration_id=pen.id,
                new_status='open'
            ).order_by(PenActivity.timestamp.desc()).first()
            
            if last_open and last_open.timestamp < threshold_time:
                pen_dict = pen.to_dict()
                pen_dict['opened_at'] = last_open.timestamp.isoformat()
                pen_dict['hours_open'] = round((datetime.utcnow() - last_open.timestamp).total_seconds() / 3600, 1)
                flagged_pens.append(pen_dict)
        
        # Sort by hours open (longest first)
        flagged_pens.sort(key=lambda x: x['hours_open'], reverse=True)
        
        return jsonify({
            'threshold_hours': threshold_hours,
            'count': len(flagged_pens),
            'penetrations': flagged_pens
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/critical-status', methods=['GET'])
@jwt_required()
def get_critical_status():
    """Get status of critical priority penetrations"""
    try:
        critical_pens = Penetration.query.filter_by(priority='critical').all()
        
        stats = {
            'total': len(critical_pens),
            'not_started': 0,
            'open': 0,
            'closed': 0,
            'verified': 0,
            'penetrations': []
        }
        
        for pen in critical_pens:
            stats[pen.status] += 1
            stats['penetrations'].append(pen.to_dict())
        
        stats['completion_rate'] = round((stats['verified'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/activity-timeline', methods=['GET'])
@jwt_required()
def get_activity_timeline():
    """Get activity timeline for a specific time period"""
    try:
        # Get date range from query params (default to last 7 days)
        days = int(request.args.get('days', 7))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        activities = PenActivity.query.filter(
            PenActivity.timestamp >= start_date
        ).order_by(PenActivity.timestamp.desc()).all()
        
        return jsonify({
            'period_days': days,
            'start_date': start_date.isoformat(),
            'total_activities': len(activities),
            'activities': [activity.to_dict() for activity in activities]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500