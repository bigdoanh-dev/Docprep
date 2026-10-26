"""Organisations, staff, learners, activation codes, tokens, consent."""
from app.db import run_sql

revision = "0002"
down_revision = "0001"

SQL = """
create table organisation (
  id serial primary key,
  code text unique not null,
  name text not null,
  region text,
  is_synthetic boolean not null default false
);

create table staff_user (
  id serial primary key,
  email text unique not null,
  password_hash text not null,
  display_name text not null,
  role text not null check (role in ('reviewer', 'admin', 'ministry_viewer')),
  active boolean not null default true,
  is_demo boolean not null default false,
  created_at timestamptz not null default now()
);

-- A learner is known everywhere by pseudonym_id. Name and contact live in learner_identity only.
create table learner (
  id serial primary key,
  pseudonym_id text unique not null,
  organisation_id int references organisation,
  audience text not null default 'student' check (audience in ('student', 'graduate')),
  focus_module_ids text[] not null default '{}',
  exam_date date not null,
  -- double precision on purpose: the API contract is a float enum, which numeric or real would not match
  target_retention double precision not null default 0.9 check (target_retention in (0.85, 0.9, 0.95)),
  new_cards_per_day int not null default 20,
  max_reviews_per_day int not null default 200,
  diagnostic_prompt_dismissed boolean not null default false,
  active boolean not null default true,
  is_synthetic boolean not null default false,
  created_at timestamptz not null default now()
);

create table learner_identity (
  learner_id int primary key references learner on delete cascade,
  display_name text not null,
  contact text
);

create table import_batch (
  id serial primary key,
  created_by int not null references staff_user,
  created_at timestamptz not null default now(),
  status text not null check (status in ('preview', 'confirmed')),
  rows jsonb not null default '[]',
  errors jsonb not null default '[]'
);

create table activation_code (
  id serial primary key,
  code_hash text unique not null,
  batch_id int references import_batch,
  organisation_id int references organisation,
  audience text not null check (audience in ('student', 'graduate')),
  issued_at timestamptz not null default now(),
  activated_at timestamptz,
  learner_id int references learner on delete set null
);

create table auth_token (
  token_hash text primary key,
  subject_type text not null check (subject_type in ('learner', 'staff')),
  subject_id int not null,
  kind text not null check (kind in ('access', 'refresh')),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index auth_token_subject_idx on auth_token (subject_type, subject_id);

create table consent_record (
  id serial primary key,
  learner_id int not null references learner on delete cascade,
  kind text not null check (kind in ('service', 'research')),
  version text not null,
  given_at timestamptz not null,
  withdrawn_at timestamptz
);

create table deletion_request (
  id serial primary key,
  learner_pid text not null,
  requested_at timestamptz not null,
  completed_at timestamptz
);
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
