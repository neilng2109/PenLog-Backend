"""PDF Report Generator for Penetration Tracking"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime
from io import BytesIO
import os
from PIL import Image as PILImage

def generate_penetration_report(project, penetrations, include_photos=True):
    """
    Generate a PDF report for penetration tracking
    
    Args:
        project: Project object
        penetrations: List of Penetration objects
        include_photos: Boolean to include photo evidence section
    
    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           rightMargin=0.75*inch, leftMargin=0.75*inch,
                           topMargin=1*inch, bottomMargin=1*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a2b3d'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#243b53'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#243b53'),
        spaceAfter=6,
        spaceBefore=6,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    
    # === COVER PAGE ===
    elements.append(Spacer(1, 2*inch))
    
    # Title
    title = Paragraph(f"<b>PENETRATION LOG REPORT</b>", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.5*inch))
    
    # Ship details
    ship_info = f"""
    <para align=center>
        <b><font size=18>{project.ship_name}</font></b><br/>
        <font size=12>{project.name}</font><br/>
        <font size=12>{project.drydock_location}</font><br/><br/>
        <font size=10>Report Generated: {datetime.now().strftime('%d %B %Y %H:%M')}</font>
    </para>
    """
    elements.append(Paragraph(ship_info, normal_style))
    elements.append(PageBreak())
    
    # === SUMMARY PAGE ===
    elements.append(Paragraph("<b>EXECUTIVE SUMMARY</b>", heading_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Calculate statistics
    total = len(penetrations)
    status_counts = {
        'not_started': 0,
        'open': 0,
        'closed': 0,
        'verified': 0
    }
    
    contractors = {}
    decks = set()
    total_photos = 0
    
    for pen in penetrations:
        status_counts[pen.status] = status_counts.get(pen.status, 0) + 1
        if pen.contractor:
            contractors[pen.contractor.name] = contractors.get(pen.contractor.name, 0) + 1
        if pen.deck:
            decks.add(pen.deck)
        # Count photos
        if hasattr(pen, 'photos'):
            # Handle both list and dynamic query
            if hasattr(pen.photos, 'count'):
                # It's a dynamic query
                total_photos += pen.photos.count()
            else:
                # It's a list
                total_photos += len(pen.photos)
    
    completion_rate = ((status_counts['closed'] + status_counts['verified']) / total * 100) if total > 0 else 0
    
    # Summary table
    summary_data = [
        ['Project Information', ''],
        ['Ship Name', project.ship_name],
        ['Drydock Location', project.drydock_location],
        ['Start Date', project.start_date.strftime('%d %B %Y') if project.start_date else 'N/A'],
        ['Embarkation Date', project.embarkation_date.strftime('%d %B %Y') if project.embarkation_date else 'N/A'],
        ['', ''],
        ['Penetration Statistics', ''],
        ['Total Penetrations', str(total)],
        ['Not Started', str(status_counts['not_started'])],
        ['Open', str(status_counts['open'])],
        ['Closed', str(status_counts['closed'])],
        ['Verified', str(status_counts['verified'])],
        ['Completion Rate', f"{completion_rate:.1f}%"],
        ['', ''],
        ['Coverage', ''],
        ['Number of Contractors', str(len(contractors))],
        ['Decks Covered', str(len(decks))],
        ['Photo Evidence Items', str(total_photos)],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#243b53')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 6), (1, 6), colors.HexColor('#243b53')),
        ('TEXTCOLOR', (0, 6), (1, 6), colors.white),
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 14), (1, 14), colors.HexColor('#243b53')),
        ('TEXTCOLOR', (0, 14), (1, 14), colors.white),
        ('FONTNAME', (0, 14), (-1, 14), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(summary_table)
    elements.append(PageBreak())
    
    # === PENETRATIONS TABLE ===
    elements.append(Paragraph("<b>PENETRATION REGISTER</b>", heading_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Table header
    pen_data = [['Pen ID', 'Deck', 'Fire Zone', 'Location', 'Type', 'Contractor', 'Status', 'Photos']]
    
    # Sort penetrations by pen_id
    sorted_pens = sorted(penetrations, key=lambda x: (x.contractor.name if x.contractor else '', x.pen_id))
    
    for pen in sorted_pens:
        status_display = {
            'not_started': 'Not Started',
            'open': 'Open',
            'closed': 'Closed',
            'verified': 'Verified'
        }.get(pen.status, pen.status)
        
        # Handle both list and dynamic query for photo count
        if hasattr(pen, 'photos'):
            if hasattr(pen.photos, 'count'):
                photo_count = pen.photos.count()
            else:
                photo_count = len(pen.photos)
        else:
            photo_count = 0
        
        pen_data.append([
            pen.pen_id or '',
            pen.deck or '',
            pen.fire_zone or '',
            pen.location or '',
            pen.pen_type or '',
            pen.contractor.name if pen.contractor else '',
            status_display,
            str(photo_count) if photo_count > 0 else '-'
        ])
    
    # Create table with appropriate column widths
    col_widths = [0.6*inch, 0.5*inch, 0.7*inch, 1.6*inch, 0.9*inch, 1.1*inch, 0.8*inch, 0.5*inch]
    pen_table = Table(pen_data, colWidths=col_widths, repeatRows=1)
    
    # Style the table
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#243b53')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (7, 0), (7, -1), 'CENTER'),  # Center photo count
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
    ]
    
    # Color-code status column
    for i, pen in enumerate(sorted_pens, 1):
        if pen.status == 'verified':
            table_style.append(('BACKGROUND', (6, i), (6, i), colors.HexColor('#d1fae5')))
            table_style.append(('TEXTCOLOR', (6, i), (6, i), colors.HexColor('#065f46')))
        elif pen.status == 'closed':
            table_style.append(('BACKGROUND', (6, i), (6, i), colors.HexColor('#dbeafe')))
            table_style.append(('TEXTCOLOR', (6, i), (6, i), colors.HexColor('#1e40af')))
        elif pen.status == 'open':
            table_style.append(('BACKGROUND', (6, i), (6, i), colors.HexColor('#fee2e2')))
            table_style.append(('TEXTCOLOR', (6, i), (6, i), colors.HexColor('#991b1b')))
    
    pen_table.setStyle(TableStyle(table_style))
    elements.append(pen_table)
    
    # === FOOTER ===
    elements.append(Spacer(1, 0.5*inch))
    footer_text = f"""
    <para align=center>
        <font size=8>
            This report was generated by PenLog Penetration Tracking System<br/>
            Report generated on {datetime.now().strftime('%d %B %Y at %H:%M')} UTC<br/>
            For official use only - SOLAS Compliance Documentation<br/>
            For complete photographic evidence, request the Excel + Photo Archive package
        </font>
    </para>
    """
    elements.append(Paragraph(footer_text, normal_style))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_contractor_report(project, contractor, penetrations):
    """Generate a contractor-specific report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           rightMargin=0.75*inch, leftMargin=0.75*inch,
                           topMargin=1*inch, bottomMargin=1*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a2b3d'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Title
    elements.append(Spacer(1, 1*inch))
    title = Paragraph(f"<b>CONTRACTOR REPORT<br/>{contractor.name}</b>", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.3*inch))
    
    # Project info
    info = f"""
    <para align=center>
        <b>{project.ship_name}</b><br/>
        {project.drydock_location}<br/>
        Report Date: {datetime.now().strftime('%d %B %Y')}
    </para>
    """
    elements.append(Paragraph(info, styles['Normal']))
    elements.append(Spacer(1, 0.5*inch))
    
    # Statistics
    total = len(penetrations)
    completed = sum(1 for p in penetrations if p.status in ['closed', 'verified'])
    
    stats_data = [
        ['Total Assigned Penetrations', str(total)],
        ['Completed', str(completed)],
        ['Completion Rate', f"{(completed/total*100):.1f}%" if total > 0 else "0%"],
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Penetrations list
    pen_data = [['Pen ID', 'Deck', 'Location', 'Type', 'Status']]
    
    for pen in sorted(penetrations, key=lambda x: x.pen_id):
        pen_data.append([
            pen.pen_id or '',
            pen.deck or '',
            pen.location or '',
            pen.pen_type or '',
            pen.status.replace('_', ' ').title()
        ])
    
    pen_table = Table(pen_data, colWidths=[1*inch, 1*inch, 2*inch, 1.5*inch, 1*inch])
    pen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#243b53')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
    ]))
    
    elements.append(pen_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer