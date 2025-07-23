#!/usr/bin/env python3
"""
Startup script that handles database migration before starting the app.
This is used as an alternative to shell scripts for better cross-platform support.
"""
import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migrations():
    """Run database migrations if needed"""
    db_path = os.environ.get('DATABASE_URL', 'sqlite:///discord_summaries.db')
    
    # Extract the actual file path from SQLite URL
    if db_path.startswith('sqlite:///'):
        db_file = db_path.replace('sqlite:///', '')
    else:
        db_file = 'discord_summaries.db'
    
    if os.path.exists(db_file):
        logger.info(f"Existing database found at {db_file}. Running migrations...")
        try:
            # Import and run migration directly
            from migrate_db import migrate_database
            if migrate_database(db_file):
                logger.info("✅ Migrations completed successfully")
            else:
                logger.error("❌ Migration failed")
                sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Error running migrations: {e}")
            # Continue anyway - the app might still work
    else:
        logger.info("No existing database found. Will create new one.")

def start_app():
    """Start the application with gunicorn"""
    logger.info("Starting Discord Summarizer with Gunicorn...")
    
    # Prepare gunicorn command
    cmd = [
        "gunicorn",
        "-w", "4",
        "-b", "0.0.0.0:5000",
        "--timeout", "3000",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "wsgi:app"
    ]
    
    # Execute gunicorn
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()
    start_app()