"""Sign-in: token families, the failed sign-in log, pseudonyms."""
from app.db import run_sql

revision = "0007"
down_revision = "0006"

SQL = """
-- The tokens of one sign-in on one device share a family. Signing out, or a refresh token presented
-- twice, revokes the family and leaves the person's other devices alone.
alter table auth_token add column family_id uuid not null;
create index auth_token_family_idx on auth_token (family_id);

-- Failed sign-ins, counted per address to slow guessing.
create table auth_failure (
  id bigserial primary key,
  ip text not null,
  kind text not null check (kind in ('activate', 'staff_login')),
  at timestamptz not null
);
create index auth_failure_ip_idx on auth_failure (ip, kind, at);

-- New learners are known as HV-001000, HV-001001, ...
create sequence learner_pseudonym_seq start 1000;
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
