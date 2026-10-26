"""Chat sessions and messages, tap-to-accept suggestions, idempotency keys, the audit log."""
from app.db import run_sql

revision = "0005"
down_revision = "0004"

SQL = """
create table chat_session (
  id serial primary key,
  learner_pid text not null,
  title text,
  kind text not null default 'chat' check (kind in ('chat', 'tutor')),
  module_id text references module,
  question_id text,   -- set when the chat was opened from a quiz item
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index chat_session_learner_idx on chat_session (learner_pid, updated_at);

-- Every answer is logged with what was retrieved, what the post-check did, and the versions that produced it.
create table chat_message (
  id serial primary key,
  session_id int not null references chat_session on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  text text not null,
  state text check (state in ('answered', 'insufficient_evidence', 'declined', 'needs_clarification')),
  format text check (format in ('text', 'table', 'calc')),
  citations jsonb,
  retrieved_passage_ids text[],
  trace jsonb,              -- the step events sent for this answer; each maps to a stage that ran
  claims_checked int,
  claims_removed int,
  notice text,
  clarifies_message_id int references chat_message,
  helpful boolean,
  model_version text,
  prompt_version text,
  corpus_version text,
  latency_ms int,
  tokens_in int,
  tokens_out int,
  cost numeric,
  is_synthetic boolean not null default false,
  created_at timestamptz not null default now()
);
create index chat_message_session_idx on chat_message (session_id, id);

-- Proposed after an answer by rules; nothing is written for the learner until accepted_at is set.
create table suggestion (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  message_id int not null references chat_message on delete cascade,
  kind text not null check (kind in ('practise', 'add_to_tomorrow')),
  competency_code text not null references competency_node,
  n_items int,
  reason_vi text not null,
  created_at timestamptz not null default now(),
  accepted_at timestamptz
);

alter table session_addition
  add constraint session_addition_suggestion_fk foreign key (suggestion_id) references suggestion on delete set null;

create table idempotency_key (
  key text not null,
  subject text not null,
  route text not null,
  status_code int not null,
  response jsonb not null,
  created_at timestamptz not null default now(),
  primary key (key, subject, route)
);

create table audit_log (
  id bigserial primary key,
  actor_type text not null,
  actor_id text,
  action text not null,
  target text,
  at timestamptz not null default now(),
  details jsonb
);

create trigger audit_log_append_only before update or delete on audit_log
  for each statement execute function forbid_change();
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
