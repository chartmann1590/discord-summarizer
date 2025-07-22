from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db, process_channel_summary
from models import AppConfig, ChannelState, Summary
from services import DiscordService, OllamaService
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Dashboard showing channels and their latest summaries"""
    config = AppConfig.get_config()
    
    if not config.is_configured():
        flash('Please configure the application first.', 'warning')
        return redirect(url_for('main.config'))
    
    # Get channel states with their latest summaries
    channels_data = []
    for channel_id in config.get_channel_ids():
        channel_state = ChannelState.query.filter_by(channel_id=channel_id).first()
        if channel_state:
            latest_summary = channel_state.summaries.first()
            channels_data.append({
                'id': channel_id,
                'state': channel_state,
                'latest_summary': latest_summary,
                'name': get_channel_name(channel_id, config.user_token)
            })
        else:
            channels_data.append({
                'id': channel_id,
                'state': None,
                'latest_summary': None,
                'name': get_channel_name(channel_id, config.user_token)
            })
    
    return render_template('dashboard.html', channels=channels_data)

@main_bp.route('/config', methods=['GET', 'POST'])
def config():
    """Configuration page"""
    config = AppConfig.get_config()
    
    if request.method == 'POST':
        # Update configuration
        config.user_token = request.form.get('user_token', '').strip()
        config.ollama_url = request.form.get('ollama_url', '').strip()
        config.model_name = request.form.get('model_name', '').strip()
        
        # Parse channel IDs
        channel_ids_raw = request.form.get('channel_ids', '')
        channel_ids = [cid.strip() for cid in channel_ids_raw.split(',') if cid.strip()]
        config.set_channel_ids(channel_ids)
        
        # Validate configuration
        errors = []
        
        if not config.user_token:
            errors.append('User token is required')
        else:
            # Test Discord connection
            discord_service = DiscordService(config.user_token)
            valid, result = discord_service.test_connection()
            if not valid:
                errors.append(f'Invalid Discord token: {result}')
        
        if not config.ollama_url:
            errors.append('Ollama URL is required')
        else:
            # Test Ollama connection
            ollama_service = OllamaService(config.ollama_url, config.model_name)
            valid, result = ollama_service.test_connection()
            if not valid:
                errors.append(f'Ollama connection failed: {result}')
        
        if not channel_ids:
            errors.append('At least one channel ID is required')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            db.session.commit()
            flash('Configuration saved successfully!', 'success')
            return redirect(url_for('main.index'))
    
    return render_template('config.html', config=config)

@main_bp.route('/run-now', methods=['POST'])
def run_now():
    """Trigger summary generation for all channels"""
    config = AppConfig.get_config()
    
    if not config.is_configured():
        return jsonify({'error': 'Application not configured'}), 400
    
    discord_service = DiscordService(config.user_token)
    ollama_service = OllamaService(config.ollama_url, config.model_name)
    
    results = []
    for channel_id in config.get_channel_ids():
        try:
            process_channel_summary(channel_id, discord_service, ollama_service)
            results.append({'channel_id': channel_id, 'status': 'success'})
        except Exception as e:
            logger.error(f"Error processing channel {channel_id}: {str(e)}")
            results.append({'channel_id': channel_id, 'status': 'error', 'error': str(e)})
    
    return jsonify({'results': results})

@main_bp.route('/channel/<channel_id>/summaries')
def channel_summaries(channel_id):
    """View all summaries for a specific channel"""
    channel_state = ChannelState.query.filter_by(channel_id=channel_id).first_or_404()
    summaries = channel_state.summaries.paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )
    
    config = AppConfig.get_config()
    channel_name = get_channel_name(channel_id, config.user_token)
    
    return render_template('channel_summaries.html', 
                         channel_id=channel_id,
                         channel_name=channel_name,
                         summaries=summaries)

@main_bp.route('/api/status')
def api_status():
    """API endpoint to check application status"""
    config = AppConfig.get_config()
    
    status = {
        'configured': config.is_configured(),
        'channels_count': len(config.get_channel_ids()),
        'total_summaries': Summary.query.count()
    }
    
    return jsonify(status)

def get_channel_name(channel_id, user_token):
    """Helper function to get channel name"""
    try:
        discord_service = DiscordService(user_token)
        channel_info = discord_service.get_channel_info(channel_id)
        if channel_info:
            return channel_info.get('name', f'Channel {channel_id}')
    except:
        pass
    return f'Channel {channel_id}'