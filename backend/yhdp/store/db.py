"""SQLite connection: WAL mode, foreign keys on, schema applied by PRAGMA user_version."""

import sqlite3
from pathlib import Path

from yhdp.settings import settings


def _script(name: str):
    return lambda con: con.executescript(Path(__file__).with_name(name).read_text(encoding="utf-8"))


# Each migration upgrades user_version i → i+1; index 0 creates the v1 schema.
MIGRATIONS = [_script("schema.sql"), _script("schema_v2_mcq.sql"), _script("schema_v3_deck.sql")]


def connect(path: Path | None = None, check_same_thread: bool = True) -> sqlite3.Connection:
    """check_same_thread=False for the web app, where FastAPI may open the per-request
    connection and run the endpoint on different worker threads."""
    path = path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=check_same_thread)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 10000")  # the tagger and the web app write concurrently
    migrate(con)
    return con


def migrate(con: sqlite3.Connection) -> None:
    version = con.execute("PRAGMA user_version").fetchone()[0]
    for i in range(version, len(MIGRATIONS)):
        MIGRATIONS[i](con)
        con.execute(f"PRAGMA user_version = {i + 1}")
    con.commit()
