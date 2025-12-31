from flask import Blueprint, send_file, jsonify, current_app
from flask_jwt_extended import jwt_required
from models import Project, Penetration, Contractor
from utils.pdf_generator import generate_penetration_report, generate_contractor_report
from utils.excel_generator import generate_penetration_excel
from utils.package_generator import generate_complete_package
from datetime import datetime

pdf_bp = Blueprint('pdf', __name__)

@pdf_bp.route('/project/<int:project_id>', methods=['GET'])
@jwt_required()
def export_project_pdf(project_id):
    """Export full project penetration report as PDF (lightweight, no photos)"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Fetch penetrations
        penetrations = Penetration.query.filter_by(project_id=project_id).all()
        
        if not penetrations:
            return jsonify({'error': 'No penetrations found for this project'}), 404
        
        # Manually load photos for each penetration (for photo count)
        from models import Photo
        for pen in penetrations:
            pen.photos = Photo.query.filter_by(penetration_id=pen.id)\
                .order_by(Photo.uploaded_at.desc()).limit(2).all()
        
        # Generate PDF without photos
        pdf_buffer = generate_penetration_report(project, penetrations, include_photos=False)
        
        # Create filename
        filename = f"PenLog_{project.ship_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@pdf_bp.route('/project/<int:project_id>/complete', methods=['GET'])
@jwt_required()
def export_complete_package(project_id):
    """Export complete package: Excel + Photo Archive in ZIP"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        penetrations = Penetration.query.filter_by(project_id=project_id).all()
        
        if not penetrations:
            return jsonify({'error': 'No penetrations found for this project'}), 404
        
        # Get upload folder from config
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Generate complete package
        zip_buffer = generate_complete_package(project, penetrations, upload_folder)
        
        # Create filename
        filename = f"PenLog_{project.ship_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}_Complete.zip"
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@pdf_bp.route('/project/<int:project_id>/excel', methods=['GET'])
@jwt_required()
def export_project_excel(project_id):
    """Export full project penetration report as Excel"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        penetrations = Penetration.query.filter_by(project_id=project_id).all()
        
        if not penetrations:
            return jsonify({'error': 'No penetrations found for this project'}), 404
        
        # Generate Excel
        excel_buffer = generate_penetration_excel(project, penetrations)
        
        # Create filename
        filename = f"PenLog_{project.ship_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@pdf_bp.route('/contractor/<int:contractor_id>', methods=['GET'])
@jwt_required()
def export_contractor_pdf(contractor_id):
    """Export contractor-specific penetration report as PDF"""
    try:
        contractor = Contractor.query.get(contractor_id)
        if not contractor:
            return jsonify({'error': 'Contractor not found'}), 404
        
        # Get the first project (you might want to make this dynamic)
        penetrations = Penetration.query.filter_by(contractor_id=contractor_id).all()
        
        if not penetrations:
            return jsonify({'error': 'No penetrations found for this contractor'}), 404
        
        project = Project.query.get(penetrations[0].project_id)
        
        # Generate PDF
        pdf_buffer = generate_contractor_report(project, contractor, penetrations)
        
        # Create filename
        filename = f"PenLog_{contractor.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500