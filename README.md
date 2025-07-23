# Discord Summarizer

A Flask-based web application that monitors Discord channels and generates hourly summaries using Ollama LLM. This application uses Discord user tokens (not bot tokens) to fetch messages and creates AI-powered summaries.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

- 🔐 Discord user token authentication
- 📊 Hourly automatic message summarization
- 🎯 Monitor multiple Discord channels
- 🏢 Server-based channel grouping
- 🤖 AI-powered summaries using Ollama
- 🎨 Automatic model detection from Ollama
- 🌐 Web dashboard with Bootstrap UI
- 🕐 Customizable timezone and time format (12/24 hour)
- 💾 SQLite database for persistence
- 🔄 Manual "Run Now" option
- ⚡ Graceful error handling and retries
- 🐳 Automatic database migration in Docker

## What's New in v2.0

- **Timezone Support**: Configure your preferred timezone and choose between 12-hour or 24-hour time format
- **Server Grouping**: Channels are now grouped by Discord server for better organization
- **Model Auto-Detection**: Automatically detects and lists all available Ollama models
- **Improved UI**: Cleaner dashboard with server-based grouping
- **Database Migration**: Automatic migration for existing installations

## Prerequisites

- Python 3.8+
- Ollama installed and running locally or on a remote server
- Discord account with access to channels you want to monitor
- At least one model installed in Ollama (e.g., `ollama pull llama3.2`)

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/chartmann1590/discord-summarizer.git
cd discord-summarizer

# Copy environment example
cp .env.example .env

# Start with Docker Compose
docker-compose up -d

# Access the application
open http://localhost:5000
```

**Note**: Database migrations are handled automatically when using Docker.

### Manual Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd discord-summarizer
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. **For existing installations**, run the migration script:
```bash
python migrate_db.py
```

**Note for Python 3.13 users**: If you encounter SQLAlchemy compatibility issues, upgrade to the latest version:
```bash
pip install --upgrade SQLAlchemy
```

## Configuration

### Getting Your Discord User Token

⚠️ **Important**: User tokens provide full access to your Discord account. Keep them secret and never share them.

1. Open Discord in your web browser (not the desktop app)
2. Press `F12` to open Developer Tools
3. Go to the **Application** tab (Chrome) or **Storage** tab (Firefox)
4. In the sidebar, expand **Local Storage** → **https://discord.com**
5. Find the entry named `token` and copy its value (without quotes)

### Getting Channel IDs

1. In Discord, go to User Settings → Advanced
2. Enable **Developer Mode**
3. Right-click on any text channel you want to monitor
4. Select **Copy Channel ID**

### Channel Configuration

You can configure channels in two ways:

1. **Basic**: Just the channel ID
   ```
   123456789012345678
   ```

2. **With Server Grouping**: Channel ID and server name
   ```
   123456789012345678,My Cool Server
   987654321098765432,Another Server
   ```

### Setting up Ollama

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Install at least one model:
```bash
ollama pull llama3.2
```
3. Ensure Ollama is running (default: http://localhost:11434)

## Running the Application

1. Start the Flask application:
```bash
python3 run.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Go to the Configuration page and set up:
   - Your Discord user token
   - Channel IDs with optional server names
   - Ollama server URL
   - Click "Load Models" to see available models
   - Select your preferred model
   - Choose your timezone and time format preference

4. Save the configuration

5. The app will automatically fetch and summarize messages every hour

## Usage

### Dashboard
- View channels grouped by Discord server
- See the latest summary for each channel
- View message counts and timestamps in your preferred timezone/format
- Click "View All Summaries" to see history

### Run Now
- Click the "Run Now" button to manually trigger summarization
- Useful for testing or getting immediate updates

### Configuration
- Update your Discord token
- Add or remove channels with server grouping
- Change Ollama settings and model selection
- Customize timezone and time format

## Environment Variables

You can set these optional environment variables:

- `SECRET_KEY`: Flask secret key (auto-generated if not set)
- `DATABASE_URL`: SQLite database path (default: `sqlite:///discord_summaries.db`)

## Project Structure

```
discord-summarizer/
├── app.py              # Main Flask application and factory
├── models.py           # Database models (with timezone support)
├── routes.py           # URL routes and views
├── services.py         # Discord and Ollama service classes
├── migrate_db.py       # Database migration script
├── startup.py          # Docker startup script with auto-migration
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
│   ├── base.html
│   ├── dashboard.html  # Server-grouped channel view
│   ├── config.html     # Enhanced configuration page
│   └── channel_summaries.html
└── README.md           # This file
```

## API Endpoints

- `GET /` - Dashboard with server grouping
- `GET /config` - Configuration page
- `POST /config` - Update configuration
- `GET /api/ollama-models` - Get available Ollama models
- `POST /run-now` - Trigger manual summary
- `GET /channel/<id>/summaries` - View channel history
- `GET /api/status` - JSON status endpoint

## Database Migration

### Automatic (Docker)
The Docker setup automatically runs migrations when starting the container.

### Manual Migration
For existing installations not using Docker:
```bash
python migrate_db.py
```

The migration script adds:
- `timezone` and `time_format_12hr` columns to the configuration
- `server_name` and `server_id` columns for channel grouping

## Security Considerations

1. **User Token Security**: 
   - Never commit your user token to version control
   - Use environment variables in production
   - Rotate tokens regularly

2. **Database Security**:
   - The SQLite database stores your token in plain text
   - Ensure proper file permissions on the database file

3. **Network Security**:
   - Use HTTPS in production
   - Consider using a reverse proxy (nginx, Apache)

## Deployment

### Using Docker

1. **Build and run with Docker:**
```bash
docker build -t discord-summarizer .
docker run -d -p 5000:5000 -v $(pwd)/data:/app/data discord-summarizer
```

2. **Using Docker Compose (recommended):**
```bash
docker-compose up -d
```

To stop:
```bash
docker-compose down
```

3. **Database Persistence:**
- The database is stored in the `./data` directory
- This directory is mounted as a volume to persist data between container restarts
- Migrations run automatically on container startup

### Using Gunicorn (Production without Docker)

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run migrations if upgrading:
```bash
python migrate_db.py
```

3. Run with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 wsgi:app
```

### Deploying to Cloud Platforms

#### Heroku
1. Create a `Procfile`:
```
release: python migrate_db.py
web: gunicorn wsgi:app
```

2. Deploy:
```bash
heroku create your-app-name
git push heroku main
```

#### Railway/Render
- Use the provided Dockerfile
- Set environment variables in the platform's dashboard
- The app will auto-deploy from your GitHub repository
- Migrations run automatically via the startup script

## Troubleshooting

### Common Issues

1. **"Invalid token" error**:
   - Ensure you copied the token correctly
   - Token might have expired - get a fresh one
   - Make sure you're using a user token, not a bot token

2. **"Cannot connect to Ollama"**:
   - Verify Ollama is running (`ollama list`)
   - Check the URL is correct
   - Click "Load Models" to verify connection and see available models

3. **No messages being fetched**:
   - Verify you have access to the channels
   - Check channel IDs are correct
   - Ensure there are new messages since last check

4. **Timezone not showing correctly**:
   - Make sure pytz is installed (`pip install pytz`)
   - Check your timezone selection in configuration

### Logs

- Application logs to stdout
- Docker logs: `docker-compose logs -f`
- Check console output for detailed error messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This application uses Discord user tokens, which is not officially supported by Discord. Use at your own risk. The authors are not responsible for any account actions taken by Discord.