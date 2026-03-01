"""
Startup migrations for SQLite.

Since create_all() won't add columns to existing tables, we use
ALTER TABLE to add new columns if they don't exist yet.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from backend.models.database import engine

logger = logging.getLogger(__name__)


def _column_exists(inspector, table: str, column: str) -> bool:
    try:
        columns = [c["name"] for c in inspector.get_columns(table)]
        return column in columns
    except Exception:
        return False


def _table_exists(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def run_migrations():
    """Run ALTER TABLE migrations for existing SQLite databases."""
    inspector = inspect(engine)

    migrations = [
        ("users", "password_hash", "VARCHAR(255)"),
        ("users", "role", "VARCHAR(20) DEFAULT 'student'"),
    ]

    with engine.begin() as conn:
        for table, column, col_type in migrations:
            if _table_exists(inspector, table) and not _column_exists(inspector, table, column):
                stmt = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                conn.execute(text(stmt))
                logger.info("Migration: added %s.%s", table, column)
