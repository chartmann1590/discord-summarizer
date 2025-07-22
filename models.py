from datetime import datetime, timezone
import json
from flask_sqlalchemy import SQLAlchemy

# Import db from app module
from app import db

class AppConfig(db.Model):
    """Application configuration stored in database"""
    id = db.Column(db.Integer, primary_key=True)
    user_token = db.Column(db.String(100), nullable=True)
    channel_ids = db.Column(db.Text, default='[]')  # JSON array of channel IDs
    ollama_url = db.Column(db.String(200), default='http://localhost:11434')
    model_name = db.Column(db.String(50), default='llama3.2')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    def get_channel_ids(self):
        """Return channel IDs as a list"""
        try:
            return json.loads(self.channel_ids) if self.channel_ids else []
        except:
            return []
    
    def set_channel_ids(self, ids_list):
        """Set channel IDs from a list"""
        self.channel_ids = json.dumps(ids_list)
    
    def is_configured(self):
        """Check if app is properly configured"""
        return bool(self.user_token and self.get_channel_ids() and self.ollama_url)
    
    @classmethod
    def get_config(cls):
        """Get the single config instance or create one"""
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config

class ChannelState(db.Model):
    """Track the last read timestamp for each channel"""
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(50), unique=True, nullable=False)
    last_read_timestamp = db.Column(db.String(50), nullable=True)  # ISO format timestamp
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship to summaries
    summaries = db.relationship('Summary', backref='channel', lazy='dynamic',
                               order_by='Summary.timestamp.desc()')

class Summary(db.Model):
    """Store generated summaries"""
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(50), db.ForeignKey('channel_state.channel_id'), nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    message_count = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def formatted_timestamp(self):
        """Return a formatted timestamp string"""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')