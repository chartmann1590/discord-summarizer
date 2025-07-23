import requests
import logging
from datetime import datetime, date
from urllib.parse import urljoin
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

logger = logging.getLogger(__name__)

class DiscordService:
    """Service for interacting with Discord API using user token"""
    BASE_URL = "https://discord.com/api/v10"
    
    def __init__(self, user_token):
        self.user_token = user_token
        self.session = self._create_session()
        self.headers = {
            "Authorization": user_token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def _create_session(self):
        """Create a session with retry logic"""
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        return session
    
    def fetch_messages(self, channel_id, limit=100, after_timestamp=None):
        """Fetch messages from a channel"""
        url = f"{self.BASE_URL}/channels/{channel_id}/messages"
        params = {"limit": limit}
        
        if after_timestamp:
            # Convert ISO timestamp to snowflake ID if needed
            if isinstance(after_timestamp, str) and '-' in after_timestamp:
                # Convert ISO to Discord snowflake
                dt = datetime.fromisoformat(after_timestamp.replace('Z', '+00:00'))
                snowflake = self._datetime_to_snowflake(dt)
                params["after"] = snowflake
            else:
                params["after"] = after_timestamp
        
        try:
            response = self.session.get(url, headers=self.headers, params=params)
            
            if response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(response.headers.get('Retry-After', 5))
                logger.warning(f"Rate limited, waiting {retry_after} seconds")
                time.sleep(retry_after)
                return self.fetch_messages(channel_id, limit, after_timestamp)
            
            response.raise_for_status()
            messages = response.json()
            
            # Sort by timestamp (oldest first)
            messages.sort(key=lambda m: m['timestamp'])
            
            return messages
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching messages from channel {channel_id}: {str(e)}")
            raise
    
    def get_channel_info(self, channel_id):
        """Get channel information including server details"""
        url = f"{self.BASE_URL}/channels/{channel_id}"
        
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            channel_data = response.json()
            
            # Try to get guild (server) information if available
            if 'guild_id' in channel_data:
                guild_info = self.get_guild_info(channel_data['guild_id'])
                if guild_info:
                    channel_data['guild_name'] = guild_info.get('name', 'Unknown Server')
                    channel_data['guild_icon'] = guild_info.get('icon')
            
            return channel_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching channel info for {channel_id}: {str(e)}")
            return None
    
    def get_guild_info(self, guild_id):
        """Get guild (server) information"""
        url = f"{self.BASE_URL}/guilds/{guild_id}"
        
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching guild info for {guild_id}: {str(e)}")
            return None
    
    def _datetime_to_snowflake(self, dt):
        """Convert datetime to Discord snowflake ID"""
        discord_epoch = 1420070400000  # Discord epoch in milliseconds
        timestamp_ms = int(dt.timestamp() * 1000)
        return str((timestamp_ms - discord_epoch) << 22)
    
    def test_connection(self):
        """Test if the user token is valid"""
        url = f"{self.BASE_URL}/users/@me"
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return True, response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to validate user token: {str(e)}")
            return False, str(e)

class OllamaService:
    """Service for interacting with Ollama API"""
    
    def __init__(self, base_url, model_name="llama3.2"):
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.session = self._create_session()
    
    def _create_session(self):
        """Create a session with appropriate timeouts"""
        session = requests.Session()
        return session
    
    def generate_summary(self, content, prompt_template=None, max_length=500):
        """Generate a summary using Ollama with custom prompt"""
        url = f"{self.base_url}/api/generate"
        
        if prompt_template:
            prompt = prompt_template.format(content=content, max_length=max_length)
        else:
            prompt = f"""Please provide a concise summary of the following Discord conversation. 
Focus on the main topics discussed, key decisions made, and important information shared. 
Keep the summary under {max_length} words.

Conversation:
{content}

Summary:"""
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": max_length
            }
        }
        
        try:
            response = self.session.post(
                url, 
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', 'Summary generation failed')
            
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            return "Summary generation timed out"
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating summary with Ollama: {str(e)}")
            return f"Error generating summary: {str(e)}"
    
    def get_available_models(self):
        """Get list of available models from Ollama"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            
            models = response.json().get('models', [])
            model_list = []
            
            for model in models:
                model_name = model.get('name', '')
                # Clean up model name (remove :latest if present)
                if ':latest' in model_name:
                    model_name = model_name.replace(':latest', '')
                
                model_list.append({
                    'name': model_name,
                    'size': model.get('size', 0),
                    'modified': model.get('modified_at', '')
                })
            
            return sorted(model_list, key=lambda x: x['name'])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get models from Ollama: {str(e)}")
            return []
    
    def test_connection(self):
        """Test if Ollama is accessible and model is available"""
        try:
            # Check if server is running
            response = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            
            # Clean up model names for comparison
            clean_model_names = []
            for name in model_names:
                if ':latest' in name:
                    clean_model_names.append(name.replace(':latest', ''))
                clean_model_names.append(name)
            
            if self.model_name in clean_model_names or any(self.model_name in name for name in clean_model_names):
                return True, f"Model {self.model_name} is available"
            else:
                available = ', '.join([m.replace(':latest', '') for m in model_names])
                return False, f"Model {self.model_name} not found. Available models: {available}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama: {str(e)}")
            return False, str(e)

class EmailService:
    """Service for sending email notifications"""
    
    def __init__(self, config):
        """Initialize with app config"""
        self.config = config
    
    def send_daily_summary_email(self, server_summaries):
        """Send daily summary email with all server summaries"""
        if not self.config.is_email_configured():
            logger.warning("Email not configured, skipping daily summary email")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Daily Discord Summary - {date.today().strftime('%B %d, %Y')}"
            msg['From'] = formataddr(('Discord Summarizer', self.config.smtp_username))
            msg['To'] = self.config.email_address
            
            # Create HTML content
            html_content = self._create_daily_summary_html(server_summaries)
            
            # Create plain text version
            text_content = self._create_daily_summary_text(server_summaries)
            
            # Attach both versions
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Daily summary email sent successfully to {self.config.email_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send daily summary email: {str(e)}")
            return False
    
    def _create_daily_summary_html(self, server_summaries):
        """Create HTML version of daily summary email"""
        today = date.today().strftime('%B %d, %Y')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #5865f2; color: white; padding: 20px; text-align: center; }}
                .server {{ margin: 20px 0; padding: 15px; border-left: 4px solid #5865f2; background-color: #f8f9fa; }}
                .channel {{ margin: 15px 0; padding: 10px; background-color: white; border-radius: 5px; }}
                .summary {{ margin: 10px 0; padding: 10px; background-color: #f1f3f4; border-radius: 3px; }}
                .meta {{ font-size: 0.9em; color: #666; margin-bottom: 5px; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Daily Discord Summary</h1>
                <p>{today}</p>
            </div>
        """
        
        if not server_summaries:
            html += "<div style='text-align: center; padding: 40px;'><p>No activity to summarize today.</p></div>"
        else:
            for server_name, channels in server_summaries.items():
                html += f"""
                <div class="server">
                    <h2>🖥️ {server_name}</h2>
                """
                
                for channel_data in channels:
                    channel_name = channel_data['name']
                    summaries = channel_data['summaries']
                    
                    html += f"""
                    <div class="channel">
                        <h3># {channel_name}</h3>
                    """
                    
                    if summaries:
                        for summary in summaries:
                            html += f"""
                            <div class="summary">
                                <div class="meta">{summary['timestamp']} • {summary['message_count']} messages</div>
                                <div>{summary['text']}</div>
                            </div>
                            """
                    else:
                        html += "<p><em>No activity today</em></p>"
                    
                    html += "</div>"
                
                html += "</div>"
        
        html += """
            <div class="footer">
                <p>This summary was generated by Discord Summarizer</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_daily_summary_text(self, server_summaries):
        """Create plain text version of daily summary email"""
        today = date.today().strftime('%B %d, %Y')
        text = f"Daily Discord Summary - {today}\n"
        text += "=" * 50 + "\n\n"
        
        if not server_summaries:
            text += "No activity to summarize today.\n"
        else:
            for server_name, channels in server_summaries.items():
                text += f"🖥️ {server_name}\n"
                text += "-" * len(server_name) + "\n\n"
                
                for channel_data in channels:
                    channel_name = channel_data['name']
                    summaries = channel_data['summaries']
                    
                    text += f"# {channel_name}\n"
                    
                    if summaries:
                        for summary in summaries:
                            text += f"  {summary['timestamp']} • {summary['message_count']} messages\n"
                            text += f"  {summary['text']}\n\n"
                    else:
                        text += "  No activity today\n\n"
        
        text += "\n" + "=" * 50 + "\n"
        text += "This summary was generated by Discord Summarizer\n"
        
        return text
    
    def test_connection(self):
        """Test SMTP connection"""
        if not self.config.is_email_configured():
            return False, "Email not configured"
        
        try:
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                server.login(self.config.smtp_username, self.config.smtp_password)
            return True, "SMTP connection successful"
        except Exception as e:
            return False, str(e)