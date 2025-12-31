from app import create_app, db
from sqlalchemy import text

app = create_app('development')

with app.app_context():
    # Create table
    db.session.execute(text("""
        CREATE TABLE access_requests (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) NOT NULL,
            company VARCHAR(200) NOT NULL,
            role VARCHAR(100) NOT NULL,
            drydock_date VARCHAR(50),
            ready_to_test BOOLEAN DEFAULT FALSE,
            message TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER REFERENCES users(id),
            notes TEXT
        )
    """))
    
    # Create indexes
    db.session.execute(text("CREATE INDEX idx_access_requests_email ON access_requests(email)"))
    db.session.execute(text("CREATE INDEX idx_access_requests_status ON access_requests(status)"))
    db.session.execute(text("CREATE INDEX idx_access_requests_created_at ON access_requests(created_at DESC)"))
    
    db.session.commit()
    print("✅ Table created successfully!")