from datetime import datetime, timezone
import json
from flask_sqlalchemy import SQLAlchemy

# Import db from app module
from app import db

try:
    import pytz
except ImportError:
    # Fallback if pytz is not installed
    pytz = None

class AppConfig(db.Model):
    """Application configuration stored in database"""
    id = db.Column(db.Integer, primary_key=True)
    user_token = db.Column(db.String(100), nullable=True)
    channel_ids = db.Column(db.Text, default='[]')  # JSON array of channel IDs
    ollama_url = db.Column(db.String(200), default='http://localhost:11434')
    model_name = db.Column(db.String(50), default='llama3.2')
    timezone = db.Column(db.String(50), default='US/Eastern')  # User's preferred timezone
    time_format_12hr = db.Column(db.Boolean, default=True)  # True for 12hr, False for 24hr
    
    # Email settings
    email_enabled = db.Column(db.Boolean, default=False)
    email_address = db.Column(db.String(100), nullable=True)  # User's email address
    smtp_server = db.Column(db.String(100), nullable=True)
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(100), nullable=True)
    smtp_password = db.Column(db.String(100), nullable=True)
    smtp_use_tls = db.Column(db.Boolean, default=True)
    daily_email_time = db.Column(db.String(5), default='09:00')  # Format: HH:MM
    
    # Custom summary prompt
    summary_prompt = db.Column(db.Text, default='''Please provide a concise summary of the following Discord conversation. 
Focus on the main topics discussed, key decisions made, and important information shared. 
Keep the summary under {max_length} words.

Conversation:
{content}

Summary:''')
    
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
    
    def is_email_configured(self):
        """Check if email is properly configured"""
        return bool(self.email_enabled and self.email_address and self.smtp_server 
                   and self.smtp_username and self.smtp_password)
    
    def format_datetime(self, dt):
        """Format datetime according to user preferences"""
        if not dt:
            return ""
        
        # If pytz is not available, use basic formatting
        if not pytz:
            if self.time_format_12hr:
                return dt.strftime('%Y-%m-%d %I:%M %p UTC')
            else:
                return dt.strftime('%Y-%m-%d %H:%M UTC')
        
        # Convert to user's timezone
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        user_tz = pytz.timezone(self.timezone)
        local_dt = dt.astimezone(user_tz)
        
        # Format based on preference
        if self.time_format_12hr:
            time_format = '%I:%M %p'  # 12-hour format
        else:
            time_format = '%H:%M'  # 24-hour format
        
        date_format = '%Y-%m-%d'
        tz_abbr = local_dt.strftime('%Z')
        
        return f"{local_dt.strftime(date_format)} {local_dt.strftime(time_format)} {tz_abbr}"
    
    def get_summary_prompt(self, content, max_length=500):
        """Get the formatted summary prompt"""
        return self.summary_prompt.format(content=content, max_length=max_length)
    
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
    server_name = db.Column(db.String(100), nullable=True)  # Discord server name
    server_id = db.Column(db.String(50), nullable=True)  # Discord server ID
    last_read_timestamp = db.Column(db.String(50), nullable=True)  # ISO format timestamp
    last_summary_date = db.Column(db.Date, nullable=True)  # Track daily summaries
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship to summaries
    summaries = db.relationship('Summary', backref='channel', lazy='dynamic',
                               order_by='Summary.timestamp.desc()')
    
    def get_display_name(self):
        """Get display name for the channel"""
        if self.server_name:
            return f"{self.server_name} - {self.channel_id}"
        return f"Channel {self.channel_id}"

class Summary(db.Model):
    """Store generated summaries"""
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(50), db.ForeignKey('channel_state.channel_id'), nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    message_count = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    summary_type = db.Column(db.String(20), default='hourly')  # 'hourly' or 'daily'
    # New field to store the original messages
    original_messages = db.Column(db.Text, nullable=True)  # JSON string of messages
    
    def formatted_timestamp(self, config=None):
        """Return a formatted timestamp string using user preferences"""
        if not config:
            config = AppConfig.get_config()
        return config.format_datetime(self.timestamp)
    
    def get_messages(self):
        """Return original messages as a list"""
        try:
            return json.loads(self.original_messages) if self.original_messages else []
        except:
            return []
    
    def set_messages(self, messages_list):
        """Set original messages from a list"""
        self.original_messages = json.dumps(messages_list)

class DailySummary(db.Model):
    """Track daily summaries that have been sent via email"""
    id = db.Column(db.Integer, primary_key=True)
    server_name = db.Column(db.String(100), nullable=False)
    server_id = db.Column(db.String(50), nullable=True)
    summary_date = db.Column(db.Date, nullable=False)
    email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))