from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db, process_channel_summary
from models import AppConfig, ChannelState, Summary
from services import DiscordService, OllamaService
import logging
import json

try:
    import pytz
except ImportError:
    pytz = None

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Dashboard showing channels and their latest summaries"""
    config = AppConfig.get_config()
    
    if not config.is_configured():
        flash('Please configure the application first.', 'warning')
        return redirect(url_for('main.config'))
    
    # Get channel states with their latest summaries, grouped by server
    servers = {}
    for channel_id in config.get_channel_ids():
        channel_state = ChannelState.query.filter_by(channel_id=channel_id).first()
        if channel_state:
            latest_summary = channel_state.summaries.first()
            server_key = channel_state.server_name or 'Ungrouped'
            
            if server_key not in servers:
                servers[server_key] = []
            
            servers[server_key].append({
                'id': channel_id,
                'state': channel_state,
                'latest_summary': latest_summary,
                'name': get_channel_name(channel_id, config.user_token)
            })
        else:
            # Channel not yet initialized
            if 'Ungrouped' not in servers:
                servers['Ungrouped'] = []
            
            servers['Ungrouped'].append({
                'id': channel_id,
                'state': None,
                'latest_summary': None,
                'name': get_channel_name(channel_id, config.user_token)
            })
    
    # Sort servers alphabetically, but keep 'Ungrouped' last
    sorted_servers = []
    for server_name in sorted(servers.keys()):
        if server_name != 'Ungrouped':
            sorted_servers.append((server_name, servers[server_name]))
    if 'Ungrouped' in servers:
        sorted_servers.append(('Ungrouped', servers['Ungrouped']))
    
    return render_template('dashboard.html', servers=sorted_servers, config=config)

@main_bp.route('/config', methods=['GET', 'POST'])
def config():
    """Configuration page"""
    config = AppConfig.get_config()
    
    if request.method == 'POST':
        # Update configuration
        config.user_token = request.form.get('user_token', '').strip()
        config.ollama_url = request.form.get('ollama_url', '').strip()
        config.model_name = request.form.get('model_name', '').strip()
        config.timezone = request.form.get('timezone', 'US/Eastern').strip()
        config.time_format_12hr = request.form.get('time_format') == '12hr'
        
        # Parse channel configuration
        channel_config = request.form.get('channel_config', '')
        channel_ids = []
        server_mappings = {}
        
        for line in channel_config.strip().split('\n'):
            if not line.strip():
                continue
            
            parts = line.strip().split(',')
            if len(parts) >= 1:
                channel_id = parts[0].strip()
                server_name = parts[1].strip() if len(parts) > 1 else None
                
                if channel_id:
                    channel_ids.append(channel_id)
                    if server_name:
                        server_mappings[channel_id] = server_name
        
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
            
            # Update channel states with server names
            for channel_id, server_name in server_mappings.items():
                channel_state = ChannelState.query.filter_by(channel_id=channel_id).first()
                if not channel_state:
                    channel_state = ChannelState(channel_id=channel_id)
                    db.session.add(channel_state)
                
                channel_state.server_name = server_name
                
                # Try to get server ID from Discord API
                if valid:  # Discord connection is valid
                    channel_info = discord_service.get_channel_info(channel_id)
                    if channel_info and 'guild_id' in channel_info:
                        channel_state.server_id = channel_info['guild_id']
                        # Use Discord server name if no custom name provided
                        if not server_name and 'guild_name' in channel_info:
                            channel_state.server_name = channel_info['guild_name']
            
            db.session.commit()
            flash('Configuration saved successfully!', 'success')
            return redirect(url_for('main.index'))
    
    # Prepare channel config for display
    channel_config_lines = []
    for channel_id in config.get_channel_ids():
        channel_state = ChannelState.query.filter_by(channel_id=channel_id).first()
        if channel_state and channel_state.server_name:
            channel_config_lines.append(f"{channel_id},{channel_state.server_name}")
        else:
            channel_config_lines.append(channel_id)
    
    channel_config_text = '\n'.join(channel_config_lines)
    
    # Get available timezones
    if pytz:
        timezones = pytz.common_timezones
    else:
        # Fallback timezones if pytz is not available
        timezones = ['UTC', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific', 
                     'Europe/London', 'Europe/Paris', 'Asia/Tokyo', 'Australia/Sydney']
    
    return render_template('config.html', 
                         config=config, 
                         channel_config=channel_config_text,
                         timezones=timezones)

@main_bp.route('/api/ollama-models')
def get_ollama_models():
    """API endpoint to get available Ollama models"""
    config = AppConfig.get_config()
    
    if not config.ollama_url:
        return jsonify({'error': 'Ollama URL not configured'}), 400
    
    ollama_service = OllamaService(config.ollama_url, config.model_name)
    models = ollama_service.get_available_models()
    
    return jsonify({'models': models})

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
    """View all summaries for a specific channel with search"""
    channel_state = ChannelState.query.filter_by(channel_id=channel_id).first_or_404()
    
    # Get search query
    search_query = request.args.get('search', '').strip()
    
    # Build query
    summaries_query = channel_state.summaries
    
    if search_query:
        # Search in summary text
        summaries_query = summaries_query.filter(
            Summary.summary_text.contains(search_query)
        )
    
    # Paginate with 5 per page
    summaries = summaries_query.paginate(
        page=request.args.get('page', 1, type=int),
        per_page=5,
        error_out=False
    )
    
    config = AppConfig.get_config()
    channel_name = get_channel_name(channel_id, config.user_token)
    
    return render_template('channel_summaries.html', 
                         channel_id=channel_id,
                         channel_name=channel_name,
                         channel_state=channel_state,
                         summaries=summaries,
                         config=config,
                         search_query=search_query)

@main_bp.route('/summary/<int:summary_id>')
def view_summary(summary_id):
    """View a single summary with original messages"""
    summary = Summary.query.get_or_404(summary_id)
    channel_state = ChannelState.query.filter_by(channel_id=summary.channel_id).first()
    config = AppConfig.get_config()
    
    channel_name = get_channel_name(summary.channel_id, config.user_token)
    
    # Get original messages
    messages = summary.get_messages()
    
    # Format timestamps in messages
    for msg in messages:
        if msg.get('timestamp'):
            try:
                dt = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                msg['formatted_timestamp'] = config.format_datetime(dt)
            except:
                msg['formatted_timestamp'] = msg['timestamp']
    
    return render_template('view_summary.html',
                         summary=summary,
                         channel_state=channel_state,
                         channel_name=channel_name,
                         messages=messages,
                         config=config)

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