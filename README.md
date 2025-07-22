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
- 🤖 AI-powered summaries using Ollama
- 🌐 Web dashboard with Bootstrap UI
- 💾 SQLite database for persistence
- 🔄 Manual "Run Now" option
- ⚡ Graceful error handling and retries

## Prerequisites

- Python 3.8+
- Ollama installed and running locally or on a remote server
- Discord account with access to channels you want to monitor
- The `llama3.2` model pulled in Ollama (`ollama pull llama3.2`)

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

### Setting up Ollama

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull the llama3.2 model:
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

3. Go to the Configuration page and enter:
   - Your Discord user token
   - Channel IDs (comma-separated)
   - Ollama server URL (default: http://localhost:11434)
   - Model name (default: llama3.2)

4. Save the configuration

5. The app will automatically fetch and summarize messages every hour

## Usage

### Dashboard
- View the latest summary for each monitored channel
- See message counts and timestamps
- Click "View All Summaries" to see history

### Run Now
- Click the "Run Now" button to manually trigger summarization
- Useful for testing or getting immediate updates

### Configuration
- Update your Discord token
- Add or remove channels
- Change Ollama settings

## Environment Variables

You can set these optional environment variables:

- `SECRET_KEY`: Flask secret key (auto-generated if not set)
- `DATABASE_URL`: SQLite database path (default: `sqlite:///discord_summaries.db`)

## Project Structure

```
discord-summarizer/
├── app.py              # Main Flask application and factory
├── models.py           # Database models
├── routes.py           # URL routes and views
├── services.py         # Discord and Ollama service classes
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── config.html
│   └── channel_summaries.html
└── README.md           # This file
```

## API Endpoints

- `GET /` - Dashboard
- `GET /config` - Configuration page
- `POST /config` - Update configuration
- `POST /run-now` - Trigger manual summary
- `GET /channel/<id>/summaries` - View channel history
- `GET /api/status` - JSON status endpoint

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

3. **Environment Variables:**
- Copy `.env.example` to `.env` and update the SECRET_KEY
- The database will be stored in the `./data` directory (persisted between container restarts)

### Using Gunicorn (Production without Docker)

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 wsgi:app
```

### Deploying to Cloud Platforms

#### Heroku
1. Create a `Procfile`:
```
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

## Troubleshooting

### Common Issues

1. **"Invalid token" error**:
   - Ensure you copied the token correctly
   - Token might have expired - get a fresh one
   - Make sure you're using a user token, not a bot token

2. **"Cannot connect to Ollama"**:
   - Verify Ollama is running (`ollama list`)
   - Check the URL is correct
   - Ensure the model is downloaded

3. **No messages being fetched**:
   - Verify you have access to the channels
   - Check channel IDs are correct
   - Ensure there are new messages since last check

### Logs

The application logs to stdout. Check console output for detailed error messages.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is provided as-is for educational purposes. Use responsibly and in accordance with Discord's Terms of Service.

## Disclaimer

This application uses Discord user tokens, which is not officially supported by Discord. Use at your own risk. The authors are not responsible for any account actions taken by Discord.