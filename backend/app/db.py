import psycopg
from psycopg.rows import dict_row

from app.config import BACKEND_DIR, env

MIGRATIONS = BACKEND_DIR / "migrations"
MIGRATE_COMMAND = "python -m app.cli migrate"


UNREACHABLE = ("Cannot reach PostgreSQL. Start it with `docker compose up -d` at the repo root "
               "(or point DATABASE_URL in .env at a local PostgreSQL 16).")


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or env("DATABASE_URL"), row_factory=dict_row)


def open_pool(url: str, min_size: int, max_size: int):
    """The server's connections. Fails fast, with the command to run, when the database is unreachable."""
    from psycopg_pool import ConnectionPool, PoolTimeout

    pool = ConnectionPool(url, min_size=min_size, max_size=max_size, kwargs={"row_factory": dict_row}, open=False)
    try:
        pool.open(wait=True, timeout=5)
    except PoolTimeout as e:
        pool.close()
        raise RuntimeError(UNREACHABLE) from e
    return pool


def _alembic_config(url: str):
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", MIGRATIONS.as_posix())
    config.attributes["url"] = url
    return config


def migrate(url: str | None = None) -> None:
    """Upgrade the database to the latest revision. Safe to repeat."""
    from alembic import command

    command.upgrade(_alembic_config(url or env("DATABASE_URL")), "head")


def head_revision() -> str:
    from alembic.script import ScriptDirectory

    return ScriptDirectory(MIGRATIONS.as_posix()).get_current_head()


def run_sql(sql: str) -> None:
    """Run a revision's SQL on the raw driver connection: with no parameters, one string may hold
    many statements and $$ function bodies."""
    from alembic import op

    op.get_bind().connection.driver_connection.execute(sql)


def pending_migrations(conn: psycopg.Connection) -> bool:
    try:
        with conn.transaction():
            row = conn.execute("select version_num from alembic_version").fetchone()
    except psycopg.errors.UndefinedTable:
        return True
    return row is None or row["version_num"] != head_revision()


def check_ready(conn: psycopg.Connection) -> None:
    """Raise a clear error when the schema is behind the code."""
    if pending_migrations(conn):
        raise RuntimeError(f"The database schema is not up to date. Run `{MIGRATE_COMMAND}` in backend/.")


def truncate_all(conn: psycopg.Connection) -> None:
    """Empty every table of the current schema except the migration bookkeeping."""
    tables = [r["table_name"] for r in conn.execute(
        """select table_name from information_schema.tables
           where table_schema = current_schema() and table_type = 'BASE TABLE' and table_name <> 'alembic_version'""")]
    if tables:
        conn.execute("truncate table " + ", ".join(f'"{t}"' for t in tables) + " restart identity cascade")
