import requests
import logging
from datetime import datetime
from urllib.parse import urljoin
import time

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
        """Get channel information"""
        url = f"{self.BASE_URL}/channels/{channel_id}"
        
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching channel info for {channel_id}: {str(e)}")
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
    
    def generate_summary(self, content, max_length=500):
        """Generate a summary using Ollama"""
        url = f"{self.base_url}/api/generate"
        
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
                timeout=120  # 2 minute timeout for generation
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
    
    def test_connection(self):
        """Test if Ollama is accessible and model is available"""
        try:
            # Check if server is running
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            
            if self.model_name in model_names or any(self.model_name in name for name in model_names):
                return True, f"Model {self.model_name} is available"
            else:
                return False, f"Model {self.model_name} not found. Available models: {', '.join(model_names)}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama: {str(e)}")
            return False, str(e)