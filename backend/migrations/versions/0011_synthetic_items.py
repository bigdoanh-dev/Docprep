"""The sample bank: questions, exam forms and documents can be flagged synthetic; the activity log is scanned by time."""
from app.db import run_sql

revision = "0011"
down_revision = "0010"

SQL = """
-- A synthetic question or form belongs to the sample cohort. It is served to synthetic learners only.
alter table question add column is_synthetic boolean not null default false;
alter table exam_form add column is_synthetic boolean not null default false;
-- A card needs a source, so a sample question cites a placeholder passage. Its document is flagged:
-- search never returns its passages and the source sheet never shows them.
alter table document add column is_synthetic boolean not null default false;

-- The ministry dashboard reads the log by period, across learners.
create index activity_event_occurred_idx on activity_event (occurred_at);
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
