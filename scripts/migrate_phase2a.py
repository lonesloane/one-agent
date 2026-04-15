"""
Phase 2A migration script - Add role column to delegates table.

This is a one-shot idempotent migration that adds the role column to the
delegates table. If the column already exists, it skips the migration and
logs the result. Uses raw SQL with SQLite-specific pragma checks.
"""

import sys
import sqlite3
from pathlib import Path
from loguru import logger


def main() -> None:
    """
    Execute Phase 2A migration - add role column to delegates table.

    Detects existing column via PRAGMA table_info and skips if present.
    Accepts database path as first CLI argument, defaults to one_agent.db.

    Raises:
        RuntimeError: If database connection or migration fails
    """
    db_path = sys.argv[1] if len(sys.argv) > 1 else "one_agent.db"

    # Resolve to absolute path
    db_file = Path(db_path).resolve()

    logger.info(f"Starting Phase 2A migration on {db_file}")

    try:
        conn = sqlite3.connect(str(db_file))
        try:
            cursor = conn.cursor()

            # Check if role column already exists
            cursor.execute("PRAGMA table_info(delegates)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            if "role" in column_names:
                logger.info(
                    "Column 'role' already exists in delegates table"
                )
                return

            # Add role column
            logger.info("Adding column 'role' to delegates table")
            cursor.execute(
                "ALTER TABLE delegates ADD COLUMN role VARCHAR "
                "NOT NULL DEFAULT 'DELEGATE'"
            )
            conn.commit()

            logger.info("Migration completed successfully")
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise RuntimeError(f"Migration failed: {e}") from e


if __name__ == "__main__":
    main()
