"""
Database connection and utility functions for price tracker.
"""

import os
import json
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Database:
    """Database manager for price tracking operations."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection parameters.

        Args:
            db_path: Path to SQLite database file. If None, uses DB_PATH from .env or default.
        """
        if db_path is None:
            db_path = os.getenv('DB_PATH', 'price_tracker.db')

        self.db_path = db_path

        # Create database file and tables if they don't exist
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database schema if tables don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")

            # Create items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    brand TEXT,
                    category TEXT,
                    scrape_frequency TEXT DEFAULT 'daily',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create price_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    colorway_name TEXT,
                    listed_price REAL,
                    sale_price REAL,
                    sizes_available TEXT,
                    screenshot_url TEXT,
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
                )
            """)

            # Create index on price_history
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_item_date
                ON price_history(item_id, scraped_at)
            """)

            # Create scrape_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success INTEGER,
                    error_message TEXT,
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
                )
            """)

            # Create extraction_recipes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS extraction_recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_domain TEXT NOT NULL,
                    recipe_version INTEGER DEFAULT 1,
                    selectors TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_successful_use TIMESTAMP,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    avg_confidence REAL,
                    UNIQUE(site_domain, recipe_version)
                )
            """)

            # Create index on extraction_recipes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_site_active
                ON extraction_recipes(site_domain, is_active)
            """)

            # Alter price_history to add extraction tracking columns
            # (use try/except since columns may already exist)
            try:
                cursor.execute("ALTER TABLE price_history ADD COLUMN extraction_method TEXT DEFAULT 'llm'")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE price_history ADD COLUMN recipe_id INTEGER")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE price_history ADD COLUMN extraction_confidence REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists

            conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            yield conn
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    # ==================== ITEMS TABLE ====================

    def add_item(self, url: str, name: str, brand: Optional[str] = None,
                 category: Optional[str] = None, scrape_frequency: str = 'daily') -> int:
        """
        Add a new item to track.

        Args:
            url: Product URL
            name: Product name
            brand: Brand name (optional)
            category: Category (optional)
            scrape_frequency: How often to scrape (default: 'daily')

        Returns:
            Item ID of newly created item
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    INSERT INTO items (url, name, brand, category, scrape_frequency)
                    VALUES (?, ?, ?, ?, ?)
                """
                cursor.execute(query, (url, name, brand, category, scrape_frequency))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Error adding item: {e}")
            finally:
                cursor.close()

    def get_item_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get item by URL."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = "SELECT * FROM items WHERE url = ?"
                cursor.execute(query, (url,))
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                cursor.close()

    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get item by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = "SELECT * FROM items WHERE id = ?"
                cursor.execute(query, (item_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                cursor.close()

    def get_all_items(self) -> List[Dict[str, Any]]:
        """Get all tracked items."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = "SELECT * FROM items ORDER BY created_at DESC"
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def add_item_if_new(self, url: str, name: str = "Auto-discovered",
                        brand: Optional[str] = None, category: Optional[str] = None) -> int:
        """
        Add item only if URL doesn't already exist.

        Returns:
            Item ID (existing or newly created)
        """
        existing = self.get_item_by_url(url)
        if existing:
            return existing['id']
        return self.add_item(url, name, brand, category)

    # ==================== PRICE HISTORY TABLE ====================

    def insert_price_record(self, item_id: int, colorway_name: Optional[str] = None,
                           listed_price: Optional[float] = None,
                           sale_price: Optional[float] = None,
                           sizes_available: Optional[List[str]] = None,
                           screenshot_url: Optional[str] = None,
                           extraction_method: Optional[str] = None,
                           recipe_id: Optional[int] = None,
                           extraction_confidence: Optional[float] = None) -> int:
        """
        Insert a price history record.

        Args:
            item_id: ID of item being tracked
            colorway_name: Color/variant name (optional)
            listed_price: Regular/original price (optional)
            sale_price: Current sale price (optional)
            sizes_available: List of available sizes (optional)
            screenshot_url: Path to screenshot (optional)
            extraction_method: 'llm' or 'direct' (optional)
            recipe_id: ID of recipe used (optional)
            extraction_confidence: Confidence score 0-1 (optional)

        Returns:
            Record ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Convert sizes list to JSON string
                sizes_json = json.dumps(sizes_available) if sizes_available else None

                query = """
                    INSERT INTO price_history
                    (item_id, colorway_name, listed_price, sale_price, sizes_available,
                     screenshot_url, extraction_method, recipe_id, extraction_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                cursor.execute(query, (
                    item_id, colorway_name, listed_price, sale_price, sizes_json,
                    screenshot_url, extraction_method, recipe_id, extraction_confidence
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Error inserting price record: {e}")
            finally:
                cursor.close()

    def get_item_history(self, item_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get price history for an item.

        Args:
            item_id: Item ID
            limit: Maximum number of records to return

        Returns:
            List of price history records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    SELECT * FROM price_history
                    WHERE item_id = ?
                    ORDER BY scraped_at DESC
                    LIMIT ?
                """
                cursor.execute(query, (item_id, limit))
                results = [dict(row) for row in cursor.fetchall()]

                # Parse JSON sizes_available back to list
                for record in results:
                    if record.get('sizes_available'):
                        record['sizes_available'] = json.loads(record['sizes_available'])

                return results
            finally:
                cursor.close()

    def get_latest_price(self, item_id: int, colorway_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get the most recent price record for an item/colorway."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if colorway_name:
                    query = """
                        SELECT * FROM price_history
                        WHERE item_id = ? AND colorway_name = ?
                        ORDER BY scraped_at DESC
                        LIMIT 1
                    """
                    cursor.execute(query, (item_id, colorway_name))
                else:
                    query = """
                        SELECT * FROM price_history
                        WHERE item_id = ?
                        ORDER BY scraped_at DESC
                        LIMIT 1
                    """
                    cursor.execute(query, (item_id,))

                row = cursor.fetchone()
                result = dict(row) if row else None
                if result and result.get('sizes_available'):
                    result['sizes_available'] = json.loads(result['sizes_available'])
                return result
            finally:
                cursor.close()

    # ==================== SCRAPE LOGS TABLE ====================

    def log_scrape(self, item_id: Optional[int], success: bool,
                   error_message: Optional[str] = None) -> int:
        """
        Log a scrape attempt.

        Args:
            item_id: Item ID (None for general errors)
            success: Whether scrape succeeded
            error_message: Error details if failed

        Returns:
            Log entry ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    INSERT INTO scrape_logs (item_id, success, error_message)
                    VALUES (?, ?, ?)
                """
                cursor.execute(query, (item_id, 1 if success else 0, error_message))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Error logging scrape: {e}")
            finally:
                cursor.close()

    def log_success(self, item_id: int) -> int:
        """Convenience method to log successful scrape."""
        return self.log_scrape(item_id, success=True)

    def log_error(self, item_id: Optional[int], error_message: str) -> int:
        """Convenience method to log failed scrape."""
        return self.log_scrape(item_id, success=False, error_message=error_message)

    def get_scrape_logs(self, item_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get scrape logs.

        Args:
            item_id: Filter by item ID (None for all items)
            limit: Maximum number of logs to return

        Returns:
            List of log entries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if item_id:
                    query = """
                        SELECT * FROM scrape_logs
                        WHERE item_id = ?
                        ORDER BY scraped_at DESC
                        LIMIT ?
                    """
                    cursor.execute(query, (item_id, limit))
                else:
                    query = """
                        SELECT * FROM scrape_logs
                        ORDER BY scraped_at DESC
                        LIMIT ?
                    """
                    cursor.execute(query, (limit,))

                return [dict(row) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def get_success_rate(self, item_id: Optional[int] = None, days: int = 7) -> float:
        """
        Calculate scrape success rate.

        Args:
            item_id: Filter by item ID (None for all items)
            days: Number of days to look back

        Returns:
            Success rate as percentage (0-100)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if item_id:
                    query = """
                        SELECT
                            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                            COUNT(*) as total
                        FROM scrape_logs
                        WHERE item_id = ? AND scraped_at >= datetime('now', '-' || ? || ' days')
                    """
                    cursor.execute(query, (item_id, days))
                else:
                    query = """
                        SELECT
                            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                            COUNT(*) as total
                        FROM scrape_logs
                        WHERE scraped_at >= datetime('now', '-' || ? || ' days')
                    """
                    cursor.execute(query, (days,))

                result = cursor.fetchone()
                if result and result[1] > 0:
                    return (result[0] / result[1]) * 100
                return 0.0
            finally:
                cursor.close()

    # ==================== EXTRACTION RECIPES TABLE ====================

    def insert_recipe(self, site_domain: str, recipe_version: int,
                     selectors: Dict[str, Any]) -> int:
        """
        Insert new extraction recipe.

        Args:
            site_domain: Site domain (e.g., 'abercrombie.com')
            recipe_version: Recipe version number
            selectors: Selector mappings dictionary

        Returns:
            Recipe ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    INSERT INTO extraction_recipes
                    (site_domain, recipe_version, selectors)
                    VALUES (?, ?, ?)
                """
                cursor.execute(query, (
                    site_domain,
                    recipe_version,
                    json.dumps(selectors)
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Error inserting recipe: {e}")
            finally:
                cursor.close()

    def get_active_recipe(self, site_domain: str) -> Optional[Dict[str, Any]]:
        """
        Get active recipe for a site.

        Args:
            site_domain: Site domain (e.g., 'abercrombie.com')

        Returns:
            Recipe dict or None if no active recipe exists
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    SELECT * FROM extraction_recipes
                    WHERE site_domain = ? AND is_active = 1
                    ORDER BY recipe_version DESC
                    LIMIT 1
                """
                cursor.execute(query, (site_domain,))
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    result['selectors'] = json.loads(result['selectors'])
                    return result
                return None
            finally:
                cursor.close()

    def get_all_recipes(self, site_domain: str) -> List[Dict[str, Any]]:
        """
        Get all recipes for a site.

        Args:
            site_domain: Site domain

        Returns:
            List of recipe dicts
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    SELECT * FROM extraction_recipes
                    WHERE site_domain = ?
                    ORDER BY recipe_version DESC
                """
                cursor.execute(query, (site_domain,))
                results = [dict(row) for row in cursor.fetchall()]
                for result in results:
                    result['selectors'] = json.loads(result['selectors'])
                return results
            finally:
                cursor.close()

    def increment_recipe_success(self, recipe_id: int, confidence: float):
        """
        Record successful extraction.

        Args:
            recipe_id: Recipe ID
            confidence: Extraction confidence score (0.0-1.0)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    UPDATE extraction_recipes
                    SET success_count = success_count + 1,
                        last_successful_use = CURRENT_TIMESTAMP,
                        avg_confidence = COALESCE(
                            (avg_confidence * success_count + ?) / (success_count + 1),
                            ?
                        )
                    WHERE id = ?
                """
                cursor.execute(query, (confidence, confidence, recipe_id))
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Error updating recipe success: {e}")
            finally:
                cursor.close()

    def increment_recipe_failure(self, recipe_id: int):
        """
        Record failed extraction.

        Args:
            recipe_id: Recipe ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    UPDATE extraction_recipes
                    SET failure_count = failure_count + 1
                    WHERE id = ?
                """
                cursor.execute(query, (recipe_id,))
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Error updating recipe failure: {e}")
            finally:
                cursor.close()

    def mark_recipe_inactive(self, recipe_id: int):
        """
        Mark recipe as inactive.

        Args:
            recipe_id: Recipe ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = "UPDATE extraction_recipes SET is_active = 0 WHERE id = ?"
                cursor.execute(query, (recipe_id,))
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                raise Exception(f"Error marking recipe inactive: {e}")
            finally:
                cursor.close()
