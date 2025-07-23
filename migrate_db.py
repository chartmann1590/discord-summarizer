#!/usr/bin/env python3
"""
Database migration script to add new columns for timezone and server support.
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
        
        # Check if columns already exist
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