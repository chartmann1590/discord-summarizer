import os
import logging
from datetime import datetime, timezone
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize extensions
db = SQLAlchemy()
scheduler = APScheduler()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///discord_summaries.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_API_ENABLED = True

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions with app
    db.init_app(app)
    scheduler.init_app(app)
    
    # Import models after db initialization
    with app.app_context():
        from models import AppConfig, ChannelState, Summary
        db.create_all()
        
    # Register blueprints
    from routes import main_bp
    app.register_blueprint(main_bp)
    
    # Start scheduler
    if not scheduler.running:
        scheduler.start()
    
    # Schedule hourly job if config exists
    @scheduler.task('interval', id='hourly_summary', hours=1, misfire_grace_time=300)
    def scheduled_summary():
        with app.app_context():
            from services import DiscordService, OllamaService
            from models import AppConfig, ChannelState, Summary
            
            config = AppConfig.get_config()
            if not config or not config.is_configured():
                logger.warning("Skipping scheduled summary - app not configured")
                return
                
            discord_service = DiscordService(config.user_token)
            ollama_service = OllamaService(config.ollama_url, config.model_name)
            
            for channel_id in config.get_channel_ids():
                try:
                    process_channel_summary(channel_id, discord_service, ollama_service)
                except Exception as e:
                    logger.error(f"Error processing channel {channel_id}: {str(e)}")
    
    return app

def process_channel_summary(channel_id, discord_service, ollama_service):
    """Process summary for a single channel"""
    from models import ChannelState, Summary
    
    # Get or create channel state
    channel_state = ChannelState.query.filter_by(channel_id=channel_id).first()
    if not channel_state:
        channel_state = ChannelState(channel_id=channel_id)
        db.session.add(channel_state)
        db.session.commit()
    
    # Fetch messages since last read
    messages = discord_service.fetch_messages(
        channel_id, 
        after_timestamp=channel_state.last_read_timestamp
    )
    
    if not messages:
        logger.info(f"No new messages in channel {channel_id}")
        return
    
    # Prepare content for summarization
    content = "\n".join([
        f"{msg['author']['username']}: {msg['content']}" 
        for msg in messages if msg.get('content')
    ])
    
    if not content.strip():
        logger.info(f"No text content to summarize in channel {channel_id}")
        return
    
    # Get summary from Ollama
    summary_text = ollama_service.generate_summary(content)
    
    # Save summary
    summary = Summary(
        channel_id=channel_id,
        summary_text=summary_text,
        message_count=len(messages),
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(summary)
    
    # Update last read timestamp
    latest_timestamp = max(msg['timestamp'] for msg in messages)
    channel_state.last_read_timestamp = latest_timestamp
    
    db.session.commit()
    logger.info(f"Successfully created summary for channel {channel_id}")

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)