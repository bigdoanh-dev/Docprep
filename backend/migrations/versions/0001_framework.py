"""The exam blueprint (HĐYKQG) and the competency tree."""
from app.db import run_sql

revision = "0001"
down_revision = None

SQL = """
create table core_issue_group (
  id int primary key,
  name text not null,
  short_name text not null,
  weight_min numeric(4,1) not null,
  weight_max numeric(4,1) not null,
  check (weight_min <= weight_max)
);

create table core_issue (
  id int primary key check (id between 1 and 54),
  group_id int not null references core_issue_group,
  name text not null
);

create table exam_competency (
  id int primary key,
  name text not null,
  weight_min numeric(4,1) not null,
  weight_max numeric(4,1) not null,
  check (weight_min <= weight_max)
);

create table exam_competency_component (
  id int primary key,
  competency_id int not null references exam_competency,
  name text not null
);

-- Topics. Mastery is tracked per node. Seeded as a provisional tree that mirrors the blueprint
-- (groups, then core issues) until the QĐ 2755/QĐ-BYT tree is available.
create table competency_node (
  code text primary key,
  parent_code text references competency_node,
  level int not null check (level between 1 and 4),
  name text not null,
  blueprint_weight double precision not null default 0,
  prerequisite_codes text[] not null default '{}',
  core_issue_id int unique references core_issue,
  provisional boolean not null default true
);
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
