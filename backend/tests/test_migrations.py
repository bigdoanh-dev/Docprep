"""Migrations: repeatable, and the server refuses to start when they are pending."""
import psycopg
import pytest

from app.config import env
from app.db import check_ready, connect, migrate, pending_migrations, truncate_all


def test_migrate_is_a_no_op_on_a_migrated_database(conn):
    before = conn.execute("select version_num from alembic_version").fetchone()["version_num"]
    migrate(env("DATABASE_URL_TEST"))
    migrate(env("DATABASE_URL_TEST"))
    assert conn.execute("select version_num from alembic_version").fetchone()["version_num"] == before


def test_a_database_stamped_0011_without_the_document_flag_gets_it(conn):
    """0011 gained `document.is_synthetic` after its first commit; 0012 adds it where it is missing."""
    conn.execute("alter table document drop column is_synthetic")
    conn.execute("update alembic_version set version_num = '0011'")
    conn.commit()
    migrate(env("DATABASE_URL_TEST"))
    column = conn.execute("""select count(*) n from information_schema.columns
                             where table_name = 'document' and column_name = 'is_synthetic'""").fetchone()["n"]
    assert column == 1 and conn.execute("select version_num from alembic_version").fetchone()["version_num"] == "0012"


def test_a_migrated_database_is_ready(conn):
    assert pending_migrations(conn) is False
    check_ready(conn)


def test_pending_migrations_refuse_to_start_and_name_the_command(conn):
    conn.execute("update alembic_version set version_num = '0000'")
    assert pending_migrations(conn) is True
    with pytest.raises(RuntimeError, match="python -m app.cli migrate"):
        check_ready(conn)
    conn.rollback()


def test_a_database_with_no_revision_table_counts_as_pending(migrated):
    with connect(env("DATABASE_URL_TEST")) as c:
        c.execute("create schema scratch")
        c.execute("set search_path to scratch")
        assert pending_migrations(c) is True
        c.rollback()


@pytest.mark.parametrize("test_url,dev_url", [
    (None, "postgresql://x/dev"),                    # unset: connect() would fall back to the dev database
    ("postgresql://x/dev", "postgresql://x/dev"),    # the same database
])
def test_the_test_session_refuses_to_drop_the_development_database(monkeypatch, test_url, dev_url):
    from tests.conftest import test_database_url
    monkeypatch.setenv("DATABASE_URL", dev_url)
    if test_url is None:
        monkeypatch.delenv("DATABASE_URL_TEST", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL_TEST", test_url)
    with pytest.raises(RuntimeError, match="DATABASE_URL_TEST"):
        test_database_url()


@pytest.mark.parametrize("value", [None, "production", "staging"])
def test_seed_commands_need_the_environment_named(monkeypatch, value):
    from app.config import require_dev_env
    if value is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", value)
    with pytest.raises(RuntimeError, match="APP_ENV"):
        require_dev_env("reset-dev")


def test_seed_commands_run_when_the_environment_is_dev_or_test(monkeypatch):
    from app.config import require_dev_env
    for value in ("dev", "test"):
        monkeypatch.setenv("APP_ENV", value)
        require_dev_env("seed")


def test_truncate_all_empties_tables_and_keeps_the_revision(conn):
    conn.execute("insert into core_issue_group values (1, 'Nhóm', 'Nhóm', 1, 2)")
    truncate_all(conn)
    assert conn.execute("select count(*) c from core_issue_group").fetchone()["c"] == 0
    assert conn.execute("select count(*) c from alembic_version").fetchone()["c"] == 1


def test_blueprint_ranges_cannot_be_inverted(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into core_issue_group values (1, 'Nhóm', 'Nhóm', 19, 17)")
