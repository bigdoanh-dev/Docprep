"""document.is_synthetic on every database stamped 0011.

Migration 0011 was edited after its first commit to add `document.is_synthetic` under the same
revision, so a database migrated with the first version is stamped 0011 without the column, and chat
search and the source sheet fail there. This adds the column where it is missing and does nothing
elsewhere.
"""
from app.db import run_sql

revision = "0012"
down_revision = "0011"

SQL = """
alter table document add column if not exists is_synthetic boolean not null default false;
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
