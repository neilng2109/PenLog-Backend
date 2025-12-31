"""
Database initialization and seeding script
Run this to set up the database with initial data
"""
# Load environment variables FIRST
from dotenv import load_dotenv
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load .env file
load_dotenv()

from app import create_app, db
from models import (User, Contractor, Penetration, Project, 
                   ContractorRegistration, ContractorAccessToken)
from werkzeug.security import generate_password_hash
from datetime import date

def init_db():
    """Initialize database tables"""
    app = create_app()
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Tables created successfully")

def seed_contractors():
    """Seed initial contractors from Crown Princess"""
    app = create_app()
    with app.app_context():
        contractors_data = [
            {'name': 'MIVAN', 'contact_person': '', 'contact_email': ''},
            {'name': 'CABLA SYSTEMS', 'contact_person': '', 'contact_email': ''},
            {'name': 'Olympus Marine', 'contact_person': '', 'contact_email': ''},
            {'name': 'MMX', 'contact_person': '', 'contact_email': ''},
            {'name': 'Century', 'contact_person': '', 'contact_email': ''},
            {'name': 'Bluestone', 'contact_person': '', 'contact_email': ''},
            {'name': 'Trident', 'contact_person': '', 'contact_email': ''},
            {'name': 'HVACON', 'contact_person': '', 'contact_email': ''},
            {'name': 'Dewave', 'contact_person': '', 'contact_email': ''},
            {'name': 'Gecom', 'contact_person': '', 'contact_email': ''},
            {'name': 'Jeumont', 'contact_person': '', 'contact_email': ''},
            {'name': 'Sinmarine', 'contact_person': '', 'contact_email': ''},
            {'name': 'Interia Idea', 'contact_person': '', 'contact_email': ''},
            {'name': 'Ship Staff', 'contact_person': '', 'contact_email': ''},
        ]
        
        print("Seeding contractors...")
        for data in contractors_data:
            contractor = Contractor.query.filter_by(name=data['name']).first()
            if not contractor:
                contractor = Contractor(**data)
                db.session.add(contractor)
                print(f"  Added: {data['name']}")
            else:
                print(f"  Skipped (exists): {data['name']}")
        
        db.session.commit()
        print("✓ Contractors seeded successfully")

def create_admin_user():
    """Create initial supervisor user"""
    app = create_app()
    with app.app_context():
        print("Creating admin user...")
        
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print("  Admin user already exists")
            return
        
        admin = User(
            username='admin',
            email='admin@penlog.io',
            password_hash=generate_password_hash('admin123'),  # Change this!
            role='supervisor'
        )
        
        db.session.add(admin)
        db.session.commit()
        print("✓ Admin user created")
        print("  Username: admin")
        print("  Password: admin123")
        print("  ⚠️  CHANGE THE PASSWORD IMMEDIATELY!")

def create_sample_project():
    """Create sample project for P&O Ventura"""
    app = create_app()
    with app.app_context():
        print("Creating sample project...")
        
        # Check if project exists
        project = Project.query.filter_by(name='P&O Ventura - Dry Dock 2026').first()
        if project:
            print("  Sample project already exists")
            return
        
        project = Project(
            name='P&O Ventura - Dry Dock 2026',
            ship_name='P&O Ventura',
            drydock_location='Hamburg Shipyard',
            start_date=date(2026, 2, 1),
            embarkation_date=date(2026, 2, 28),
            status='active',
            notes='February 2026 drydock period'
        )
        
        db.session.add(project)
        db.session.commit()
        print("✓ Sample project created")
        print(f"  Project ID: {project.id}")
        print(f"  Ship: {project.ship_name}")
        print(f"  Location: {project.drydock_location}")

def reset_db():
    """Drop and recreate all tables (DESTRUCTIVE!)"""
    app = create_app()
    with app.app_context():
        response = input("⚠️  This will DELETE ALL DATA. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        
        print("Dropping all tables...")
        db.drop_all()
        print("Creating tables...")
        db.create_all()
        print("✓ Database reset complete")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python utils/init_db.py init         - Create tables")
        print("  python utils/init_db.py seed         - Seed contractors")
        print("  python utils/init_db.py admin        - Create admin user")
        print("  python utils/init_db.py project      - Create sample project")
        print("  python utils/init_db.py reset        - Reset database (DESTRUCTIVE)")
        print("  python utils/init_db.py all          - Run init + seed + admin + project")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'init':
        init_db()
    elif command == 'seed':
        seed_contractors()
    elif command == 'admin':
        create_admin_user()
    elif command == 'project':
        create_sample_project()
    elif command == 'reset':
        reset_db()
    elif command == 'all':
        init_db()
        seed_contractors()
        create_admin_user()
        create_sample_project()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)