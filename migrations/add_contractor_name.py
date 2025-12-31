"""Add contractor_name to pen_activities table"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Add contractor_name column
    try:
        with db.engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE pen_activities 
                ADD COLUMN contractor_name VARCHAR(100)
            """))
            conn.commit()
        print("✅ Successfully added contractor_name column to pen_activities table")
    except Exception as e:
        if "already exists" in str(e) or "duplicate" in str(e).lower():
            print("⚠️  Column contractor_name already exists")
        else:
            print(f"❌ Error: {e}")
            raise