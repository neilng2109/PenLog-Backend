from flask import Blueprint, send_file, jsonify, current_app
from flask_jwt_extended import jwt_required
from models import Project, Penetration, Contractor
from utils.pdf_generator import generate_penetration_report, generate_contractor_report
from utils.excel_generator import generate_penetration_excel
from utils.package_generator import generate_complete_package
from datetime import datetime

pdf_bp = Blueprint('pdf', __name__)

# Excel export endpoint (matches frontend call to /api/pdf/project/:id/excel)
@pdf_bp.route('/project/<int:project_id>/excel', methods=['OPTIONS'])
def excel_options(project_id):
    """Handle OPTIONS preflight for Excel export"""
    return '', 204

@pdf_bp.route('/project/<int:project_id>/excel', methods=['GET'])
@jwt_required()
def export_excel(project_id):
    """Export Excel with Cloudinary photo links"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        penetrations = Penetration.query.filter_by(project_id=project_id).all()
        
        if not penetrations:
            return jsonify({'error': 'No penetrations found for this project'}), 404
        
        # Get upload folder from config (not used for Cloudinary but kept for backward compatibility)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Generate complete package (now returns Excel with Cloudinary links)
        excel_buffer = generate_complete_package(project, penetrations, upload_folder)
        
        # Create filename
        filename = f"PenLog_{project.ship_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}_Complete.xlsx"
        
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# PDF export endpoint (matches frontend call to /api/pdf/project/:id)
@pdf_bp.route('/project/<int:project_id>', methods=['OPTIONS'])
def pdf_options(project_id):
    """Handle OPTIONS preflight for PDF export"""
    return '', 204

@pdf_bp.route('/project/<int:project_id>', methods=['GET'])
@jwt_required()
def export_pdf(project_id):
    """Export PDF report"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        penetrations = Penetration.query.filter_by(project_id=project_id).all()
        
        if not penetrations:
            return jsonify({'error': 'No penetrations found for this project'}), 404
        
        # Generate PDF report
        pdf_buffer = generate_penetration_report(project, penetrations)
        
        # Create filename
        filename = f"PenLog_{project.ship_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}_Report.pdf"
        
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

# Keep the old endpoint for backward compatibility
@pdf_bp.route('/project/<int:project_id>/complete', methods=['OPTIONS'])
def complete_options(project_id):
    """Handle OPTIONS preflight for complete package"""
    return '', 204

@pdf_bp.route('/project/<int:project_id>/complete', methods=['GET'])
@jwt_required()
def export_complete_package(project_id):
    """Export complete package: Excel with Cloudinary photo links (legacy endpoint)"""
    return export_excel(project_id)