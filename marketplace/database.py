"""Small request-scoped SQLite helpers for the local marketplace."""

import sqlite3
from pathlib import Path

from flask import current_app, g
from marketplace.migrations import apply_migrations


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"], timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error=None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    get_db().executescript(schema_path.read_text(encoding="utf-8"))
    get_db().commit()
    apply_migrations(get_db())
