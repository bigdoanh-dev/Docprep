"""${message}"""
from app.db import run_sql

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}

SQL = """
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
