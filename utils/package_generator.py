"""Complete Package Generator - Excel + Photo Archive"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
from io import BytesIO
import os
import shutil
import zipfile
from pathlib import Path

def generate_complete_package(project, penetrations, upload_folder):
    """
    Generate complete package: Excel with data + organized photo folders + hyperlinks
    
    Args:
        project: Project object
        penetrations: List of Penetration objects
        upload_folder: Path to uploads folder where photos are stored
    
    Returns:
        BytesIO object containing the zip file
    """
    # Create temporary directory for package
    import tempfile
    temp_dir = tempfile.mkdtemp()
    package_name = f"PenLog_{project.ship_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
    package_dir = os.path.join(temp_dir, package_name)
    os.makedirs(package_dir)
    
    # Create photos directory
    photos_dir = os.path.join(package_dir, 'photos')
    os.makedirs(photos_dir)
    
    # === CREATE EXCEL FILE ===
    wb = Workbook()
    ws = wb.active
    ws.title = "Penetrations with Photos"
    
    # Colors
    navy_fill = PatternFill(start_color="243b53", end_color="243b53", fill_type="solid")
    teal_fill = PatternFill(start_color="14b8a6", end_color="14b8a6", fill_type="solid")
    light_gray_fill = PatternFill(start_color="f0f4f8", end_color="f0f4f8", fill_type="solid")
    white_font = Font(color="FFFFFF", bold=True, size=11)
    bold_font = Font(bold=True, size=11)
    link_font = Font(color="0563C1", underline="single", size=10)
    
    # Headers
    headers = ['Pen ID', 'Deck', 'Fire Zone', 'Location', 'Type', 'Contractor', 
               'Status', 'Opening Photo', 'Closing Photo', 'Photo Folder']
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col)
        cell.value = header
        cell.font = white_font
        cell.fill = navy_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Sort penetrations
    sorted_pens = sorted(penetrations, key=lambda x: (x.contractor.name if x.contractor else '', x.pen_id))
    
    # Process each penetration
    for row_idx, pen in enumerate(sorted_pens, 2):
        # Create folder for this pen
        folder_name = f"{pen.pen_id}_{pen.deck}_{pen.location.replace(' ', '_').replace('/', '-')[:30]}"
        pen_folder = os.path.join(photos_dir, folder_name)
        os.makedirs(pen_folder, exist_ok=True)
        
        # Basic pen info
        ws.cell(row=row_idx, column=1, value=pen.pen_id or '')
        ws.cell(row=row_idx, column=2, value=pen.deck or '')
        ws.cell(row=row_idx, column=3, value=pen.fire_zone or '')
        ws.cell(row=row_idx, column=4, value=pen.location or '')
        ws.cell(row=row_idx, column=5, value=pen.pen_type or '')
        ws.cell(row=row_idx, column=6, value=pen.contractor.name if pen.contractor else '')
        
        # Status with color
        status_display = {
            'not_started': 'Not Started',
            'open': 'Open',
            'closed': 'Closed',
            'verified': 'Verified'
        }.get(pen.status, pen.status)
        
        status_cell = ws.cell(row=row_idx, column=7, value=status_display)
        
        if pen.status == 'verified':
            status_cell.fill = PatternFill(start_color="d1fae5", end_color="d1fae5", fill_type="solid")
            status_cell.font = Font(color="065f46", bold=True)
        elif pen.status == 'closed':
            status_cell.fill = PatternFill(start_color="dbeafe", end_color="dbeafe", fill_type="solid")
            status_cell.font = Font(color="1e40af", bold=True)
        elif pen.status == 'open':
            status_cell.fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")
            status_cell.font = Font(color="991b1b", bold=True)
        
        # Get photos for this pen
        from models import Photo
        photos = Photo.query.filter_by(penetration_id=pen.id).order_by(Photo.uploaded_at).all()
        
        opening_photo = None
        closing_photo = None
        
        # Copy photos to pen folder and categorize
        for idx, photo in enumerate(photos):
            if os.path.exists(photo.filepath):
                # Determine photo type
                photo_type = photo.photo_type or 'general'
                
                # Generate filename
                ext = os.path.splitext(photo.filename)[1]
                if 'opening' in photo_type.lower() or (not closing_photo and idx == 0):
                    new_filename = f"opening{ext}"
                    opening_photo = new_filename
                elif 'closing' in photo_type.lower() or (not opening_photo and idx == 0):
                    new_filename = f"closing{ext}"
                    closing_photo = new_filename
                else:
                    new_filename = f"photo_{idx + 1}{ext}"
                
                # Copy photo to pen folder
                dest_path = os.path.join(pen_folder, new_filename)
                shutil.copy2(photo.filepath, dest_path)
                
                # If we don't have opening/closing yet, assign first two
                if idx == 0 and not opening_photo:
                    opening_photo = new_filename
                elif idx == 1 and not closing_photo:
                    closing_photo = new_filename
        
        # Add hyperlinks to photos
        if opening_photo:
            opening_cell = ws.cell(row=row_idx, column=8)
            opening_cell.value = "View Opening"
            # Use relative path that works after extraction
            opening_cell.hyperlink = f"photos/{folder_name}/{opening_photo}"
            opening_cell.font = link_font
            opening_cell.alignment = Alignment(horizontal='center')
        else:
            ws.cell(row=row_idx, column=8, value="-")
            ws.cell(row=row_idx, column=8).alignment = Alignment(horizontal='center')
        
        if closing_photo:
            closing_cell = ws.cell(row=row_idx, column=9)
            closing_cell.value = "View Closing"
            # Use relative path that works after extraction
            closing_cell.hyperlink = f"photos/{folder_name}/{closing_photo}"
            closing_cell.font = link_font
            closing_cell.alignment = Alignment(horizontal='center')
        else:
            ws.cell(row=row_idx, column=9, value="-")
            ws.cell(row=row_idx, column=9).alignment = Alignment(horizontal='center')
        
        # Folder link - add note that folder must be opened manually
        folder_cell = ws.cell(row=row_idx, column=10)
        folder_cell.value = folder_name
        folder_cell.alignment = Alignment(horizontal='center')
        folder_cell.font = Font(size=9, italic=True, color="666666")
        
        # Alternating row colors
        if row_idx % 2 == 0:
            for col in range(1, 11):
                if col not in [7, 8, 9, 10]:  # Don't override status/link colors
                    ws.cell(row=row_idx, column=col).fill = light_gray_fill
    
    # Column widths
    column_widths = [12, 8, 12, 25, 15, 20, 12, 15, 15, 15]
    for idx, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    
    # Freeze top row
    ws.freeze_panes = 'A2'
    
    # Add instructions sheet
    ws_instructions = wb.create_sheet("Instructions", 0)
    
    instructions_text = [
        ["PenLog Complete Package", ""],
        ["", ""],
        ["IMPORTANT: EXTRACT THE ZIP FILE FIRST!", ""],
        ["Excel hyperlinks only work after extracting the zip.", ""],
        ["", ""],
        ["CONTENTS:", ""],
        ["1. This Excel file with penetration data", ""],
        ["2. Photos folder organized by pen", ""],
        ["", ""],
        ["HOW TO USE:", ""],
        ["1. Extract the complete zip file to a folder", ""],
        ["2. Open this Excel file from the extracted folder", ""],
        ["3. Enable editing if prompted by Excel", ""],
        ["4. Click blue 'View Opening' or 'View Closing' links", ""],
        ["5. Or manually browse the 'photos' folder", ""],
        ["", ""],
        ["TROUBLESHOOTING:", ""],
        ["- If links don't work: Check you extracted the zip first", ""],
        ["- If Excel blocks links: Click 'Enable Editing' at top", ""],
        ["- Alternative: Navigate to photos folder manually", ""],
        ["", ""],
        ["FOLDER STRUCTURE:", ""],
        ["photos/", ""],
        ["  ├── 001_Deck5_Gym/", ""],
        ["  │   ├── opening.jpg", ""],
        ["  │   └── closing.jpg", ""],
        ["  ├── 002_Deck6_EngineRoom/", ""],
        ["  │   ├── opening.jpg", ""],
        ["  │   └── closing.jpg", ""],
        ["", ""],
        ["PROJECT INFORMATION:", ""],
        ["Ship:", project.ship_name],
        ["Drydock:", project.drydock_location],
        ["Generated:", datetime.now().strftime('%d %B %Y %H:%M UTC')],
    ]
    
    for row_idx, row_data in enumerate(instructions_text, 1):
        ws_instructions.cell(row=row_idx, column=1, value=row_data[0])
        ws_instructions.cell(row=row_idx, column=2, value=row_data[1])
        
        if row_idx == 1:
            ws_instructions.cell(row=row_idx, column=1).font = Font(bold=True, size=16, color="243b53")
        elif ":" in row_data[0] and row_data[0].isupper():
            ws_instructions.cell(row=row_idx, column=1).font = Font(bold=True, size=12)
    
    ws_instructions.column_dimensions['A'].width = 40
    ws_instructions.column_dimensions['B'].width = 40
    
    # Save Excel file
    excel_path = os.path.join(package_dir, f"{package_name}.xlsx")
    wb.save(excel_path)
    
    # === CREATE ZIP FILE ===
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add Excel file
        zipf.write(excel_path, f"{package_name}/{package_name}.xlsx")
        
        # Add all photos
        for root, dirs, files in os.walk(photos_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join(package_name, os.path.relpath(file_path, package_dir))
                zipf.write(file_path, arcname)
    
    # Cleanup temp directory
    shutil.rmtree(temp_dir)
    
    zip_buffer.seek(0)
    return zip_buffer