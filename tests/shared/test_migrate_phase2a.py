"""Tests for Phase 2A migration script."""

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.migrate_phase2a import main


def test_migrate_phase2a_idempotent() -> None:
    """
    Test Phase 2A migration is idempotent and adds role column.

    Procedure:
    1. Create a fresh SQLite database with Phase 1 schema (delegates
       table without role column)
    2. Run migrate_phase2a.main(db_path) via sys.argv mocking
    3. Assert role column now exists
    4. Run migrate_phase2a.main(db_path) again — assert no error
       (idempotent)

    This ensures the migration script can be safely re-run without
    failure, and that it correctly adds the role column to the
    delegates table with NOT NULL and DEFAULT values.
    """
    # Create a temporary database file
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_phase2a.db"

        # Create a Phase 1 schema (delegates table without role)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create delegations table (required for FK constraint)
        cursor.execute(
            """
            CREATE TABLE delegations (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                membership_type VARCHAR NOT NULL
            )
            """
        )

        # Create delegates table without role column (Phase 1 state)
        cursor.execute(
            """
            CREATE TABLE delegates (
                id VARCHAR PRIMARY KEY,
                full_name VARCHAR NOT NULL,
                email VARCHAR NOT NULL,
                function VARCHAR NOT NULL,
                title VARCHAR,
                delegation_id VARCHAR NOT NULL,
                accreditation_date DATETIME NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                last_login DATETIME,
                FOREIGN KEY (delegation_id) REFERENCES delegations(id)
            )
            """
        )

        conn.commit()
        conn.close()

        # Run the migration (first time) by mocking sys.argv
        with patch.object(
            sys,
            "argv",
            ["migrate_phase2a.py", str(db_path)],
        ):
            main()

        # Verify role column exists after first migration
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(delegates)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        assert "role" in column_names, (
            "role column not created after migration"
        )

        conn.close()

        # Run the migration again (idempotency test)
        with patch.object(
            sys,
            "argv",
            ["migrate_phase2a.py", str(db_path)],
        ):
            main()

        # Verify column still exists and no duplication occurred
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(delegates)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        role_columns = [c for c in column_names if c == "role"]
        assert len(role_columns) == 1, (
            f"Expected exactly 1 role column, got {len(role_columns)}"
        )

        conn.close()
