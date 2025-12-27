#!/usr/bin/env python3
"""
View the database schema and sample data.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from dotenv import load_dotenv

load_dotenv()


def main():
    db_path = os.getenv('DB_PATH', 'price_tracker.db')
    db = Database(db_path)

    print("=" * 70)
    print(f"Database Schema: {db_path}")
    print("=" * 70)
    print()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            if table == 'sqlite_sequence':
                continue  # Skip internal SQLite table

            print(f"Table: {table}")
            print("-" * 70)

            # Get table schema
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()

            # Print column info
            print(f"{'Column':<20} {'Type':<15} {'Nullable':<10} {'Default':<15} {'PK'}")
            print("-" * 70)

            for col in columns:
                col_id, name, col_type, not_null, default_val, pk = col
                nullable = "NOT NULL" if not_null else "NULL"
                default = str(default_val) if default_val else "-"
                primary_key = "PRIMARY KEY" if pk else ""

                print(f"{name:<20} {col_type:<15} {nullable:<10} {default:<15} {primary_key}")

            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fks = cursor.fetchall()

            if fks:
                print()
                print("Foreign Keys:")
                for fk in fks:
                    fk_id, seq, ref_table, from_col, to_col, on_update, on_delete, match = fk
                    print(f"  {from_col} -> {ref_table}({to_col}) ON DELETE {on_delete}")

            # Get indexes
            cursor.execute(f"PRAGMA index_list({table})")
            indexes = cursor.fetchall()

            if indexes:
                print()
                print("Indexes:")
                for idx in indexes:
                    seq, name, unique, origin, partial = idx
                    unique_str = "UNIQUE" if unique else ""
                    print(f"  {name} {unique_str}")

            # Show sample data
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            print()
            print(f"Row count: {count}")

            if count > 0:
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                rows = cursor.fetchall()

                print()
                print("Sample data (first 3 rows):")
                col_names = [col[1] for col in columns]
                print("  " + " | ".join(col_names[:5]))  # Show first 5 columns
                print("  " + "-" * 60)

                for row in rows:
                    # Truncate long values
                    row_str = []
                    for val in row[:5]:
                        val_str = str(val)
                        if len(val_str) > 15:
                            val_str = val_str[:12] + "..."
                        row_str.append(val_str)
                    print("  " + " | ".join(row_str))

            print()
            print("=" * 70)
            print()

        cursor.close()


if __name__ == "__main__":
    main()
