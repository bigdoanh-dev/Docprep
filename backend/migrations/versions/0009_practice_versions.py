"""A practice set records which version of each question it serves, and what it will be compared with."""
from app.db import run_sql

revision = "0009"
down_revision = "0008"

SQL = """
-- question id -> version, fixed when the set is built: a question edited or retired afterwards is
-- still shown and scored as the learner saw it, as in an exam attempt.
-- baseline: the learner's top-priority topic just before the set's first answer, {"top_topic": code};
-- the adaptation summary says the order changed only if it differs afterwards.
alter table practice_set
  add column question_versions jsonb not null default '{}',
  add column baseline jsonb;
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
