"""Knowledge base, glossary, học phần, question bank, exam forms, review. The approval rule."""
from app.db import run_sql

revision = "0003"
down_revision = "0002"

ITEM_STATUS = "('draft', 'prescreen', 'in_review_r1', 'in_review_r2', 'approved', 'needs_revision', 'rejected', 'retired')"

SQL = f"""
create table document (
  id text primary key,
  title text not null,
  edition text,
  version int not null default 1,
  validity_status text not null default 'valid',
  validity_note text,
  excerpt_limit int,
  demo_label text not null
);

create table passage (
  id text primary key,
  document_id text not null references document,
  chapter text,
  lesson text,
  section text,
  page_start int,
  page_end int,
  article text,
  competency_code text references competency_node,
  content_type text,
  scope_of_use text,
  validity_status text not null default 'valid',
  version int not null default 1,
  text text not null,
  text_unaccented text not null,
  corpus_version text not null,
  -- context = document title, chapter and section, searchable alongside the passage text
  context text not null default '',
  context_unaccented text not null default '',
  tsv tsvector generated always as (to_tsvector('simple',
    text || ' ' || text_unaccented || ' ' || context || ' ' || context_unaccented)) stored
);
create index passage_tsv_idx on passage using gin (tsv);

create table glossary_term (
  id serial primary key,
  term text not null,
  synonyms text[] not null default '{{}}',
  status text not null default 'approved',
  -- an expert-flagged ambiguous term makes the chat ask which sense is meant
  ambiguous boolean not null default false,
  sense_group text
);

-- Học phần: the eight blueprint groups.
create table module (
  id text primary key,
  name text not null,
  short_name text not null,
  ord int not null,
  core_issue_group_id int references core_issue_group,
  competency_codes text[] not null default '{{}}',
  coming_soon boolean not null default false
);

-- Questions and content items are versioned: an edit is a new version, nothing is deleted.
create table content_item (
  id text not null,
  version int not null default 1,
  title text,
  body text not null,
  source_passage_ids text[] not null default '{{}}',
  status text not null check (status in {ITEM_STATUS}),
  ai_assisted boolean not null default false,
  primary key (id, version)
);

create table question (
  id text not null,
  version int not null default 1,
  type text not null default 'mcq',
  stem text not null,
  options jsonb not null,
  explanation text not null,
  rubric jsonb,
  competency_code text not null references competency_node,
  core_issue_id int references core_issue,
  exam_competency_component_id int references exam_competency_component,
  bloom_level int not null check (bloom_level between 1 and 3),
  difficulty_label text not null,
  difficulty_b double precision not null,
  n_responses int not null default 0,
  source_passage_ids text[] not null,
  status text not null check (status in {ITEM_STATUS}),
  ai_assisted boolean not null default false,
  author text,
  primary key (id, version)
);

create table unit (
  id text primary key,
  module_id text not null references module,
  ord int not null,
  topic text not null,
  competency_code text not null references competency_node
);

-- content_id and question_id have no foreign key: their targets have composite keys. The loader checks them.
create table unit_item (
  id text primary key,
  unit_id text not null references unit,
  ord int not null,
  kind text not null check (kind in ('content', 'quiz', 'remediation')),
  content_id text,
  question_id text,
  after_item_id text,
  note text
);

-- kind 'assembled': question_ids is empty and each attempt gets n_questions chosen for the learner.
create table exam_form (
  id text primary key,
  title text not null,
  kind text not null check (kind in ('diagnostic', 'mock', 'demo_short', 'assembled')),
  question_ids text[] not null,
  n_questions int,
  seconds_per_question int not null,
  max_attempts int,
  status text not null
);

create table review_decision (
  id serial primary key,
  target_type text not null check (target_type in ('question', 'content')),
  target_id text not null,
  version int not null,
  round int not null check (round in (1, 2)),
  reviewer_id int not null references staff_user,
  decision text not null check (decision in ('pass', 'revise', 'reject')),
  comment text,
  created_at timestamptz not null default now(),
  check (decision = 'pass' or btrim(coalesce(comment, '')) <> '')
);
create index review_decision_target_idx on review_decision (target_type, target_id, version);

create table status_transition (
  id bigserial primary key,
  target_type text not null check (target_type in ('question', 'content')),
  target_id text not null,
  version int not null,
  from_status text,
  to_status text not null,
  actor_id int references staff_user,
  actor_label text not null,
  at timestamptz not null default now(),
  reason text
);
create index status_transition_target_idx on status_transition (target_type, target_id, version);

create table error_report (
  id serial primary key,
  target_type text not null check (target_type in ('question', 'answer', 'card', 'content')),
  target_id text not null,
  reason text not null check (reason in ('wrong_content', 'wrong_citation', 'broken_item', 'inappropriate', 'other')),
  note text,
  learner_pid text not null,
  context jsonb,
  status text not null default 'open' check (status in ('open', 'resolved')),
  created_at timestamptz not null default now()
);

-- Human in the loop: nothing becomes approved without a pass in each review round, by different reviewers.
create function approved_requires_two_reviews() returns trigger language plpgsql as $$
declare
  reviewed boolean;
begin
  if new.status <> 'approved' then
    return new;
  end if;
  if tg_op = 'UPDATE' and old.status = 'approved' then
    return new;
  end if;
  select exists (
    select 1
    from review_decision r1
    join review_decision r2
      on r2.target_type = r1.target_type and r2.target_id = r1.target_id and r2.version = r1.version
    where r1.target_type = tg_argv[0] and r1.target_id = new.id and r1.version = new.version
      and r1.round = 1 and r1.decision = 'pass'
      and r2.round = 2 and r2.decision = 'pass'
      and r1.reviewer_id <> r2.reviewer_id
  ) into reviewed;
  if not reviewed then
    raise exception 'approved needs a pass in round 1 and round 2 from different reviewers';
  end if;
  return new;
end $$;

create trigger question_approval before insert or update on question
  for each row execute function approved_requires_two_reviews('question');
create trigger content_item_approval before insert or update on content_item
  for each row execute function approved_requires_two_reviews('content');

-- Append-only tables refuse any update or delete, even one that would touch no row. Truncate stays
-- possible: tests and the dev reset rely on it.
create function forbid_change() returns trigger language plpgsql as $$
begin
  raise exception '% is append-only', tg_table_name;
end $$;

create trigger status_transition_append_only before update or delete on status_transition
  for each statement execute function forbid_change();
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
