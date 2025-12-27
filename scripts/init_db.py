#!/usr/bin/env python3
"""
Database initialization script for price tracker.
Creates SQLite database and all necessary tables.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    """Main initialization flow."""
    print("=" * 50)
    print("Price Tracker Database Initialization (SQLite)")
    print("=" * 50)
    print()

    # Get database path
    db_path = os.getenv('DB_PATH', 'price_tracker.db')

    print(f"Database file: {db_path}")
    print()

    try:
        # Initialize database (creates file and tables automatically)
        print("Initializing database...")
        db = Database(db_path)
        print("✓ Database initialized successfully!")
        print()

        # Verify tables
        print("Verifying tables...")
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = ['items', 'price_history', 'scrape_logs']
            missing_tables = set(expected_tables) - set(tables)

            if missing_tables:
                print(f"✗ Missing tables: {missing_tables}")
                sys.exit(1)
            else:
                print(f"✓ Found all {len(expected_tables)} required tables:")
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"  - {table} ({count} rows)")
                cursor.close()

        print()
        print("=" * 50)
        print("✓ Database initialization complete!")
        print("=" * 50)
        print()
        print(f"Database location: {os.path.abspath(db_path)}")

    except Exception as e:
        print()
        print("=" * 50)
        print(f"✗ Database initialization failed!")
        print(f"Error: {e}")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
