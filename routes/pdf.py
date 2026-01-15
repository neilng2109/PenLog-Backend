@pdf_bp.route('/project/<int:project_id>/complete', methods=['GET'])
@jwt_required()
def export_complete_package(project_id):
    """Export complete package: Excel with Cloudinary photo links"""
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