"""Private learner credentials; usernames never enter learner/model payloads."""
from app.db import run_sql

revision = "0016"
down_revision = "0015"


def upgrade():
    run_sql("""
    create table learner_credential (
      learner_id int primary key references learner on delete cascade,
      username text unique not null check (username ~ '^[a-z0-9][a-z0-9._-]{2,63}$'),
      password_hash text not null,
      changed_at timestamptz not null default now()
    );
    revoke all on learner_credential from public;
    alter table auth_failure drop constraint auth_failure_kind_check;
    alter table auth_failure add constraint auth_failure_kind_check
      check (kind in ('activate', 'staff_login', 'learner_login'));
    """)


def downgrade():
    raise NotImplementedError("forward-only")
