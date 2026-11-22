"""Pedagogy inputs for the chat tutor, both MACHINE-MADE and UNREVIEWED (decided 2026-11-23):

- question_bloom_label: a six-level Bloom label per question version, kept apart from
  question.bloom_level_6 (which stays for reviewed labels; an approved question cannot be edited).
  Filled by experiments/bloom_labels/apply.py.
- competency_node.prerequisite_codes: filled from config/prerequisites.yaml where still empty
  (app/prerequisites.py; the blueprint seed applies the same map to a fresh tree).
"""
from app.db import run_sql
from app.prerequisites import statements

revision = "0021"
down_revision = "0020"


def upgrade():
    run_sql("""
    create table question_bloom_label (
      question_id text not null,
      question_version int not null,
      level smallint not null check (level between 1 and 6),
      source text not null default 'machine' check (source in ('machine', 'reviewed')),
      created_at timestamptz not null default now(),
      primary key (question_id, question_version),
      foreign key (question_id, question_version) references question (id, version)
    );
    """)
    for sql in statements():
        run_sql(sql)


def downgrade():
    raise NotImplementedError("forward-only")
