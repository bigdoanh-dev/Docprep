"""Learner records: mastery, unit sessions, exam attempts, practice sets, responses, cards, daily sessions, activity."""
from app.db import run_sql

revision = "0004"
down_revision = "0003"

SQL = """
create table mastery (
  learner_id int not null references learner on delete cascade,
  competency_code text not null references competency_node,
  theta double precision not null default 0,
  n_responses int not null default 0,
  updated_at timestamptz,
  primary key (learner_id, competency_code)
);

create table unit_session (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  unit_id text not null references unit,
  queue text[] not null,
  cursor int not null default 0,
  cards_created int not null default 0,
  done boolean not null default false,
  started_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table exam_attempt (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  form_id text not null references exam_form,
  question_order text[] not null,
  option_orders jsonb not null,
  started_at timestamptz not null,
  deadline_at timestamptz not null,
  submitted_at timestamptz,
  auto_submitted boolean not null default false,
  score int,
  summary jsonb,
  assembly jsonb   -- for assembled forms: how this attempt's questions were chosen
);

create table attempt_answer (
  attempt_id int not null references exam_attempt on delete cascade,
  question_id text not null,
  chosen text,
  flagged boolean not null default false,
  changes int not null default 0,
  updated_at timestamptz not null default now(),
  primary key (attempt_id, question_id)
);

-- A small list of approved questions on one competency: the daily session's step 2, an accepted chat
-- suggestion, or "Làm câu tương tự". summary is the stored adaptation summary.
create table practice_set (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  source text not null check (source in ('session', 'chat_suggestion', 'quiz_similar')),
  competency_code text not null references competency_node,
  question_ids text[] not null,
  reasons jsonb not null default '{}',
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  summary jsonb
);

create table item_response (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  question_id text not null,
  question_version int not null,
  context text not null check (context in ('unit', 'practice', 'diagnostic', 'mock')),
  attempt_id int,
  unit_session_id int,
  unit_item_id text,
  practice_set_id int references practice_set,
  chosen text,
  correct boolean not null,
  card_id int,
  time_ms int,
  created_at timestamptz not null default now()
);
create unique index item_response_unit_once on item_response (unit_session_id, unit_item_id)
  where unit_session_id is not null;
create index item_response_learner_idx on item_response (learner_id, created_at);

create table card (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  source_question_id text not null,
  source_context text not null,
  front text not null,
  back text not null,
  citation text not null,
  fsrs_card jsonb not null,
  due_at timestamptz not null,
  reps int not null default 0,
  lapses int not null default 0,
  suspended boolean not null default false,
  created_by text not null default 'rule',
  created_at timestamptz not null default now(),
  unique (learner_id, source_question_id)
);

create table card_review (
  id serial primary key,
  card_id int not null references card on delete cascade,
  rating int not null check (rating between 1 and 4),
  reviewed_at timestamptz not null,
  scheduled_seconds int not null,
  time_ms int
);

-- The session as built for the learner's local day, so it does not shift while they work through it.
create table daily_session (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  local_date date not null,
  steps jsonb not null,
  practice_set_id int references practice_set on delete set null,
  built_at timestamptz not null default now(),
  unique (learner_id, local_date)
);

create table session_addition (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  for_date date not null,
  competency_code text not null references competency_node,
  suggestion_id int,
  created_at timestamptz not null default now()
);

-- One narrow log for usage figures, the research export, Tiến độ · Nhịp học and the Home suggestions.
-- Keyed by pseudonym, never by name.
create table activity_event (
  id bigserial primary key,
  learner_pid text not null,
  kind text not null check (kind in ('visit', 'unit_response', 'practice_response', 'exam_started',
    'exam_submitted', 'card_review', 'chat_turn', 'session_step_completed', 'cards_created',
    'remediation_inserted', 'practice_set_built')),
  occurred_at timestamptz not null,
  duration_ms int,
  ref_type text,
  ref_id text,
  is_synthetic boolean not null default false
);
create index activity_event_learner_idx on activity_event (learner_pid, occurred_at);

create trigger activity_event_append_only before update or delete on activity_event
  for each statement execute function forbid_change();
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
