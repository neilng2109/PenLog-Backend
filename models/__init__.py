from datetime import datetime
from app import db
import secrets

# Association table for many-to-many relationship between projects and contractors
project_contractors = db.Table('project_contractors',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True),
    db.Column('contractor_id', db.Integer, db.ForeignKey('contractors.id'), primary_key=True),
    db.Column('added_at', db.DateTime, default=datetime.utcnow)
)

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    ship_name = db.Column(db.String(200), nullable=False)
    drydock_location = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    embarkation_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), default='active')
    notes = db.Column(db.Text)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    invite_code = db.Column(db.String(32), unique=True, index=True)  # ADD THIS LINE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    penetrations = db.relationship('Penetration', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    supervisor = db.relationship('User', backref='supervised_projects')
    
    def generate_invite_code(self):
        """Generate a unique invite code for contractor registration"""
        self.invite_code = secrets.token_urlsafe(16)  # Generates a 16-character URL-safe code
        return self.invite_code
    
    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'name': self.name,
            'ship_name': self.ship_name,
            'drydock_location': self.drydock_location,
            'start_date': self.start_date.isoformat(),
            'embarkation_date': self.embarkation_date.isoformat(),
            'status': self.status,
            'notes': self.notes,
            'supervisor_id': self.supervisor_id,
            'invite_code': self.invite_code,  # ADD THIS LINE
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_stats:
            data['stats'] = {
                'total_penetrations': self.penetrations.count(),
                'not_started': self.penetrations.filter_by(status='not_started').count(),
                'open': self.penetrations.filter_by(status='open').count(),
                'closed': self.penetrations.filter_by(status='closed').count(),
                'verified': self.penetrations.filter_by(status='verified').count()
            }
        
        return data

class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='contractor')  # supervisor, contractor
    contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    contractor = db.relationship('Contractor', backref='users')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'contractor_id': self.contractor_id,
            'contractor_name': self.contractor.name if self.contractor else None
        }

class Contractor(db.Model):
    """Contractor companies"""
    __tablename__ = 'contractors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    contact_person = db.Column(db.String(100))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'contact_person': self.contact_person,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'active': self.active
        }

class Penetration(db.Model):
    """Penetration/pen records"""
    __tablename__ = 'penetrations'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    pen_id = db.Column(db.String(20), nullable=False)  # e.g., "PEN-001" or "001"
    deck = db.Column(db.String(50), nullable=False)
    fire_zone = db.Column(db.String(20))  # e.g., "FZ-3", "FZ-1"
    frame = db.Column(db.String(20))  # e.g., "42", "38"
    location = db.Column(db.String(200))
    pen_type = db.Column(db.String(50))  # e.g., MCT, Roxtec, GK, Navicross, Fire Seal
    size = db.Column(db.String(50))
    contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'))
    status = db.Column(db.String(20), default='not_started')  # not_started, open, closed, verified
    priority = db.Column(db.String(20), default='routine')  # critical, important, routine
    opened_at = db.Column(db.DateTime)  # When pen was opened
    completed_at = db.Column(db.DateTime)  # When pen was closed/completed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    contractor = db.relationship('Contractor', backref='penetrations')
    activities = db.relationship('PenActivity', backref='penetration', lazy='dynamic', 
                                cascade='all, delete-orphan')
    photos = db.relationship('Photo', backref='penetration', lazy='dynamic',
                            cascade='all, delete-orphan')
    
    # Unique constraint on pen_id per project per contractor
    __table_args__ = (
        db.UniqueConstraint('project_id', 'contractor_id', 'pen_id', name='unique_pen_per_contractor'),
    )
    
    def to_dict(self, include_activities=False, include_photos=False):
        data = {
            'id': self.id,
            'project_id': self.project_id,
            'pen_id': self.pen_id,
            'deck': self.deck,
            'fire_zone': self.fire_zone,
            'frame': self.frame,
            'location': self.location,
            'pen_type': self.pen_type,
            'size': self.size,
            'contractor_id': self.contractor_id,
            'contractor_name': self.contractor.name if self.contractor else None,
            'status': self.status,
            'priority': self.priority,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'photo_count': self.photos.count()  # Add photo count
        }
        
        if include_activities:
            data['activities'] = [a.to_dict() for a in self.activities.order_by(PenActivity.timestamp.desc())]
        
        if include_photos:
            data['photos'] = [p.to_dict() for p in self.photos.order_by(Photo.uploaded_at.desc())]
            
        return data

class PenActivity(db.Model):
    """Activity log for each penetration"""
    __tablename__ = 'pen_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    penetration_id = db.Column(db.Integer, db.ForeignKey('penetrations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    contractor_name = db.Column(db.String(100))  # For magic link submissions
    action = db.Column(db.String(20), nullable=False)  # opened, closed, verified, noted
    previous_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'penetration_id': self.penetration_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else self.contractor_name,
            'action': self.action,
            'previous_status': self.previous_status,
            'new_status': self.new_status,
            'notes': self.notes,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class Photo(db.Model):
    """Photos associated with penetrations"""
    __tablename__ = 'photos'
    
    id = db.Column(db.Integer, primary_key=True)
    penetration_id = db.Column(db.Integer, db.ForeignKey('penetrations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    cloudinary_public_id = db.Column(db.String(500)) 
    caption = db.Column(db.String(200))
    photo_type = db.Column(db.String(20), default='general')  # before, after, issue, general
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'penetration_id': self.penetration_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'filename': self.filename,
            'filepath': self.filepath,
            'cloudinary_public_id': self.cloudinary_public_id,
            'caption': self.caption,
            'photo_type': self.photo_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

class ContractorRegistration(db.Model):
    """Pending contractor registrations for approval"""
    __tablename__ = 'contractor_registrations'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100), nullable=False)
    contact_email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    reviewer = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'company_name': self.company_name,
            'contact_person': self.contact_person,
            'contact_email': self.contact_email,
            'status': self.status,
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewed_by': self.reviewed_by
        }

class ContractorAccessToken(db.Model):
    """Magic links for contractor access without login"""
    __tablename__ = 'contractor_access_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    contractor = db.relationship('Contractor')
    
    @staticmethod
    def generate_token():
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    def is_valid(self):
        """Check if token is still valid"""
        if not self.active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'contractor_id': self.contractor_id,
            'contractor_name': self.contractor.name if self.contractor else None,
            'token': self.token,
            'active': self.active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'link': f'/report/{self.token}'
        }

class AccessRequest(db.Model):
    """Access requests from landing page"""
    __tablename__ = 'access_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    drydock_date = db.Column(db.String(50))
    ready_to_test = db.Column(db.Boolean, default=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, contacted, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    
    reviewer = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'company': self.company,
            'role': self.role,
            'drydock_date': self.drydock_date,
            'ready_to_test': self.ready_to_test,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewer': self.reviewer.username if self.reviewer else None,
            'notes': self.notes
        }