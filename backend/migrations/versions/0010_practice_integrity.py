"""Findings of the phase 5A review: one answer per question of a practice set; an unused column goes."""
from app.db import run_sql

revision = "0010"
down_revision = "0009"

SQL = """
-- A question of a practice set is answered once. The service locks the set row while answering;
-- this index is the database's own word on it, as item_response_unit_once is for unit quizzes.
create unique index item_response_practice_once on item_response (practice_set_id, question_id)
  where practice_set_id is not null;

-- The adaptation summary no longer compares with a stored snapshot: it compares the learner's record
-- with and without the set's own answers.
alter table practice_set drop column baseline;
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
