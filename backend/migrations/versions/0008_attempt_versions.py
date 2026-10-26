"""Finding of the phase 4A review: an attempt records which version of each question it serves."""
from app.db import run_sql

revision = "0008"
down_revision = "0007"

SQL = """
-- question id -> version, fixed when the attempt starts. A question edited or retired while the
-- attempt runs is still shown, scored and reviewed as the learner saw it. Attempts started before
-- this column existed have '{}' and fall back to the version that was approved.
alter table exam_attempt add column question_versions jsonb not null default '{}';
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
