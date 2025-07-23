import os
import logging
from datetime import datetime, timezone, timedelta, date, time
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
        from models import AppConfig, ChannelState, Summary, DailySummary
        db.create_all()
        
    # Register blueprints
    from routes import main_bp
    app.register_blueprint(main_bp)
    
    # Start scheduler
    if not scheduler.running:
        scheduler.start()
    
    # Schedule hourly job for summaries
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
                    process_channel_summary(channel_id, discord_service, ollama_service, config)
                except Exception as e:
                    logger.error(f"Error processing channel {channel_id}: {str(e)}")
    
    # Schedule daily email job
    @scheduler.task('cron', id='daily_email', hour=9, minute=0, misfire_grace_time=3600)
    def scheduled_daily_email():
        with app.app_context():
            send_daily_email_summary()
    
    return app

def process_channel_summary(channel_id, discord_service, ollama_service, config):
    """Process summary for a single channel with improved duplicate prevention"""
    from models import ChannelState, Summary
    
    # Get or create channel state
    channel_state = ChannelState.query.filter_by(channel_id=channel_id).first()
    if not channel_state:
        channel_state = ChannelState(channel_id=channel_id)
        db.session.add(channel_state)
        db.session.commit()
    
    # Check when the last summary was created (improved logic)
    current_time = datetime.now(timezone.utc)
    
    # Check if we already have a summary in the last hour
    one_hour_ago = current_time - timedelta(hours=1)
    recent_summary = Summary.query.filter(
        Summary.channel_id == channel_id,
        Summary.timestamp > one_hour_ago,
        Summary.summary_type == 'hourly'
    ).first()
    
    if recent_summary:
        logger.info(f"Skipping channel {channel_id} - summary already exists from {recent_summary.timestamp}")
        return
    
    # Determine the timestamp to fetch messages from
    fetch_after_timestamp = channel_state.last_read_timestamp
    
    # If we have any previous hourly summary, use its timestamp as starting point
    last_hourly_summary = Summary.query.filter(
        Summary.channel_id == channel_id,
        Summary.summary_type == 'hourly'
    ).order_by(Summary.timestamp.desc()).first()
    
    if last_hourly_summary:
        # Ensure the timestamp is timezone-aware
        last_summary_time = last_hourly_summary.timestamp
        if last_summary_time.tzinfo is None:
            last_summary_time = last_summary_time.replace(tzinfo=timezone.utc)
        
        # Convert summary timestamp to ISO format string for Discord API
        last_summary_iso = last_summary_time.isoformat().replace('+00:00', 'Z')
        
        # Use the later of the two timestamps
        if not fetch_after_timestamp or last_summary_iso > fetch_after_timestamp:
            fetch_after_timestamp = last_summary_iso
    
    # Fetch messages since last read or last summary
    messages = discord_service.fetch_messages(
        channel_id, 
        after_timestamp=fetch_after_timestamp
    )
    
    if not messages:
        logger.info(f"No new messages in channel {channel_id} since {fetch_after_timestamp}")
        return
    
    # Prepare content for summarization
    content = "\n".join([
        f"{msg['author']['username']}: {msg['content']}" 
        for msg in messages if msg.get('content')
    ])
    
    if not content.strip():
        logger.info(f"No text content to summarize in channel {channel_id}")
        return
    
    # Get summary from Ollama using custom prompt
    summary_text = ollama_service.generate_summary(
        content, 
        config.summary_prompt, 
        max_length=500
    )
    
    # Prepare messages for storage (only essential fields)
    stored_messages = []
    for msg in messages:
        stored_messages.append({
            'id': msg.get('id'),
            'author': {
                'username': msg['author'].get('username', 'Unknown'),
                'id': msg['author'].get('id'),
                'avatar': msg['author'].get('avatar')
            },
            'content': msg.get('content'),
            'timestamp': msg.get('timestamp'),
            'attachments': [{'url': att.get('url'), 'filename': att.get('filename')} 
                          for att in msg.get('attachments', [])]
        })
    
    # Save summary
    summary = Summary(
        channel_id=channel_id,
        summary_text=summary_text,
        message_count=len(messages),
        timestamp=current_time,
        summary_type='hourly'
    )
    summary.set_messages(stored_messages)
    db.session.add(summary)
    
    # Update last read timestamp to the latest message
    latest_timestamp = max(msg['timestamp'] for msg in messages)
    channel_state.last_read_timestamp = latest_timestamp
    
    db.session.commit()
    logger.info(f"Successfully created hourly summary for channel {channel_id} with {len(messages)} messages")

def send_daily_email_summary():
    """Send daily email summary to user"""
    from models import AppConfig, ChannelState, Summary, DailySummary
    from services import EmailService, DiscordService
    
    config = AppConfig.get_config()
    if not config.is_email_configured():
        logger.info("Email not configured, skipping daily email")
        return
    
    today = date.today()
    
    # Check if we already sent today's email
    existing_email = DailySummary.query.filter_by(
        summary_date=today,
        email_sent=True
    ).first()
    
    if existing_email:
        logger.info(f"Daily email already sent for {today}")
        return
    
    # Get current time in user's timezone
    try:
        import pytz
        user_tz = pytz.timezone(config.timezone)
        current_time = datetime.now(user_tz).time()
        
        # Parse the configured email time
        email_time_parts = config.daily_email_time.split(':')
        email_time = time(int(email_time_parts[0]), int(email_time_parts[1]))
        
        # Only send if it's the right time (within 1 hour window)
        time_diff = datetime.combine(today, current_time) - datetime.combine(today, email_time)
        if abs(time_diff.total_seconds()) > 3600:  # More than 1 hour difference
            logger.info(f"Not time for daily email yet. Current: {current_time}, Scheduled: {email_time}")
            return
    except:
        # If timezone handling fails, just proceed
        pass
    
    # Group channels by server and collect summaries from last 24 hours
    server_summaries = {}
    discord_service = DiscordService(config.user_token)
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    for channel_id in config.get_channel_ids():
        channel_state = ChannelState.query.filter_by(channel_id=channel_id).first()
        if not channel_state:
            continue
        
        # Get server name
        server_name = channel_state.server_name or 'Ungrouped'
        if server_name not in server_summaries:
            server_summaries[server_name] = []
        
        # Get channel name
        try:
            channel_info = discord_service.get_channel_info(channel_id)
            channel_name = channel_info.get('name', f'Channel {channel_id}') if channel_info else f'Channel {channel_id}'
        except:
            channel_name = f'Channel {channel_id}'
        
        # Get summaries from last 24 hours
        daily_summaries = Summary.query.filter(
            Summary.channel_id == channel_id,
            Summary.timestamp > yesterday,
            Summary.summary_type == 'hourly'
        ).order_by(Summary.timestamp.asc()).all()
        
        # Format summaries for email
        formatted_summaries = []
        for summary in daily_summaries:
            formatted_summaries.append({
                'text': summary.summary_text,
                'timestamp': config.format_datetime(summary.timestamp),
                'message_count': summary.message_count
            })
        
        server_summaries[server_name].append({
            'name': channel_name,
            'id': channel_id,
            'summaries': formatted_summaries
        })
    
    # Send email
    email_service = EmailService(config)
    success = email_service.send_daily_summary_email(server_summaries)
    
    if success:
        # Mark as sent for each server
        for server_name in server_summaries.keys():
            daily_summary = DailySummary(
                server_name=server_name,
                summary_date=today,
                email_sent=True,
                email_sent_at=datetime.now(timezone.utc)
            )
            db.session.add(daily_summary)
        
        db.session.commit()
        logger.info(f"Daily email summary sent successfully for {today}")
    else:
        logger.error(f"Failed to send daily email summary for {today}")

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)