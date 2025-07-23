#!/usr/bin/env python3
"""
Database migration script to add new columns for timezone, server support, email settings, and custom prompts.
Run this script after updating to the new version.
"""
import sqlite3
import sys
import os

def migrate_database(db_path='discord_summaries.db'):
    """Add new columns to existing database"""
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. No migration needed.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Starting database migration...")
        
        # Check if columns already exist in app_config
        cursor.execute("PRAGMA table_info(app_config)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add timezone column to app_config if it doesn't exist
        if 'timezone' not in columns:
            print("Adding timezone column to app_config...")
            cursor.execute("ALTER TABLE app_config ADD COLUMN timezone VARCHAR(50) DEFAULT 'US/Eastern'")
            print("✓ Added timezone column")
        
        # Add time_format_12hr column to app_config if it doesn't exist
        if 'time_format_12hr' not in columns:
            print("Adding time_format_12hr column to app_config...")
            cursor.execute("ALTER TABLE app_config ADD COLUMN time_format_12hr BOOLEAN DEFAULT 1")
            print("✓ Added time_format_12hr column")
        
        # Add email settings columns
        email_columns = [
            ('email_enabled', 'BOOLEAN DEFAULT 0'),
            ('email_address', 'VARCHAR(100)'),
            ('smtp_server', 'VARCHAR(100)'),
            ('smtp_port', 'INTEGER DEFAULT 587'),
            ('smtp_username', 'VARCHAR(100)'),
            ('smtp_password', 'VARCHAR(100)'),
            ('smtp_use_tls', 'BOOLEAN DEFAULT 1'),
            ('daily_email_time', 'VARCHAR(5) DEFAULT "09:00"'),
        ]
        
        for col_name, col_def in email_columns:
            if col_name not in columns:
                print(f"Adding {col_name} column to app_config...")
                cursor.execute(f"ALTER TABLE app_config ADD COLUMN {col_name} {col_def}")
                print(f"✓ Added {col_name} column")
        
        # Add summary_prompt column
        if 'summary_prompt' not in columns:
            print("Adding summary_prompt column to app_config...")
            # SQLite doesn't support parameterized defaults in ALTER TABLE
            # So we'll add the column without default and then update existing rows
            cursor.execute("ALTER TABLE app_config ADD COLUMN summary_prompt TEXT")
            
            # Set default value for existing rows
            default_prompt = '''Please provide a concise summary of the following Discord conversation. 
Focus on the main topics discussed, key decisions made, and important information shared. 
Keep the summary under {max_length} words.

Conversation:
{content}

Summary:'''
            cursor.execute("UPDATE app_config SET summary_prompt = ? WHERE summary_prompt IS NULL", (default_prompt,))
            print("✓ Added summary_prompt column")
        
        # Check channel_state columns
        cursor.execute("PRAGMA table_info(channel_state)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add server_name column to channel_state if it doesn't exist
        if 'server_name' not in columns:
            print("Adding server_name column to channel_state...")
            cursor.execute("ALTER TABLE channel_state ADD COLUMN server_name VARCHAR(100)")
            print("✓ Added server_name column")
        
        # Add server_id column to channel_state if it doesn't exist
        if 'server_id' not in columns:
            print("Adding server_id column to channel_state...")
            cursor.execute("ALTER TABLE channel_state ADD COLUMN server_id VARCHAR(50)")
            print("✓ Added server_id column")
        
        # Add last_summary_date column to channel_state if it doesn't exist
        if 'last_summary_date' not in columns:
            print("Adding last_summary_date column to channel_state...")
            cursor.execute("ALTER TABLE channel_state ADD COLUMN last_summary_date DATE")
            print("✓ Added last_summary_date column")
        
        # Check summary columns
        cursor.execute("PRAGMA table_info(summary)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add original_messages column to summary if it doesn't exist
        if 'original_messages' not in columns:
            print("Adding original_messages column to summary...")
            cursor.execute("ALTER TABLE summary ADD COLUMN original_messages TEXT")
            print("✓ Added original_messages column")
        
        # Add summary_type column to summary if it doesn't exist
        if 'summary_type' not in columns:
            print("Adding summary_type column to summary...")
            cursor.execute("ALTER TABLE summary ADD COLUMN summary_type VARCHAR(20) DEFAULT 'hourly'")
            print("✓ Added summary_type column")
        
        # Create daily_summary table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name VARCHAR(100) NOT NULL,
                server_id VARCHAR(50),
                summary_date DATE NOT NULL,
                email_sent BOOLEAN DEFAULT 0,
                email_sent_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Created/verified daily_summary table")
        
        conn.commit()
        print("\n✅ Database migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"\n❌ Error during migration: {e}")
        return False
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Try common locations
        if os.path.exists('discord_summaries.db'):
            db_path = 'discord_summaries.db'
        elif os.path.exists('data/discord_summaries.db'):
            db_path = 'data/discord_summaries.db'
        elif os.path.exists('/app/data/discord_summaries.db'):
            db_path = '/app/data/discord_summaries.db'
        else:
            print("Could not find database. Please specify path as argument.")
            print("Usage: python migrate_db.py [path/to/discord_summaries.db]")
            sys.exit(1)
    
    print(f"Migrating database: {db_path}")
    migrate_database(db_path)