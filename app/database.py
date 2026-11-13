from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator

BASE_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = BASE_DIR.parent / "migrations"
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR.parent / "buddy_quest.db"))


@contextmanager
def connect(database_path: Path = DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path: Path = DATABASE_PATH) -> None:
    with connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = migration_path.name
            applied = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (version,),
            ).fetchone()
            if applied:
                continue
            connection.executescript(migration_path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
